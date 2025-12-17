import os
import shutil
import uuid
from typing import List
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from pypdf import PdfReader
import logging
import numpy as np
import requests
from bs4 import BeautifulSoup


from .Db.models import Document, DocumentChunk, ProcessingStatus
from . import rag_service

logger = logging.getLogger(__name__)

TEMP_UPLOAD_DIR = "/tmp/rag_uploads"

# Load embedder lazily
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("SentenceTransformer not installed. Mocking embedding generation.")
            def mock_embed(text, **kwargs):
                return np.random.rand(len(text), 384)
            _embedder = type("MockEmbedder", (object,), {"encode": mock_embed})
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}. Mocking embedding generation.")
            def mock_embed(text, **kwargs):
                return np.random.rand(len(text), 384)
            _embedder = type("MockEmbedder", (object,), {"encode": mock_embed})
    return _embedder


def _get_temp_file_path(filename: str) -> str:
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4()}_{filename}"
    return os.path.join(TEMP_UPLOAD_DIR, unique_name)


def _read_and_clean_pdf(file_path: str) -> str:
    full_text = []
    try:
        with open(file_path, "rb") as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)

        return "\n".join(full_text)

    except Exception as e:
        logger.error(f"Error processing PDF file {file_path}: {e}")
        raise


def _chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    if not text:
        return []

    chunks = []
    i = 0
    while i < len(text):
        end = i + chunk_size
        chunks.append(text[i:end])
        i += (chunk_size - chunk_overlap)
        if end >= len(text):
            break

    return chunks


def _generate_and_save_chunks(db: Session, document_id: str, text: str):
    chunks = _chunk_text(text)
    chunk_contents = [c for c in chunks if c.strip()]

    if not chunk_contents:
        logger.warning(f"No usable content for document {document_id}")
        return

    embedder = get_embedder()
    embeddings = embedder.encode(chunk_contents, convert_to_numpy=True, show_progress_bar=False)

    for i, (content, embedding) in enumerate(zip(chunk_contents, embeddings)):
        new_chunk = DocumentChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=document_id,
            content=content,
            embedding=str(embedding.tolist()),
            chunk_index=i
        )
        db.add(new_chunk)

    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if doc:
        doc.processing_status = ProcessingStatus.READY

    db.commit()


def process_document(db: Session, document_id: str, conversation_id: str | None, text: str):
    _generate_and_save_chunks(db, document_id, text)
    if conversation_id:
        rag_service.link_documents_to_conversation(db, conversation_id, document_id)


async def process_document_upload(db: Session, user_id: str, conversation_id: str | None, file: UploadFile) -> str:
    temp_file_path = _get_temp_file_path(file.filename)
    document_id = None

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document = rag_service.create_document_and_link(db, user_id, file.filename)
        document_id = document.document_id

        document.processing_status = ProcessingStatus.CHUNKING
        db.commit()

        text_content = _read_and_clean_pdf(temp_file_path)

        # Call processing including linking
        process_document(db, document_id, conversation_id, text_content)


        logger.info(f"Document {document_id} processed successfully.")
        return document_id

    except Exception as e:
        logger.error(f"Failed to process document {file.filename}: {e}")

        if document_id:
            doc = db.query(Document).filter(Document.document_id == document_id).first()
            if doc:
                doc.processing_status = ProcessingStatus.FAILED
                db.commit()

        raise HTTPException(status_code=500, detail=f"Document processing failed: {e}")

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def process_url(db: Session, user_id: str, conversation_id: str | None, url: str) -> str:
    document_id = None
    try:
        # Fetch URL content
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text()
        
        # Clean text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Create document
        title = soup.title.string if soup.title else url
        document = rag_service.create_document_and_link(db, user_id, f"WEB: {title}")
        document.storage_path = url # Store URL as storage path
        document_id = document.document_id
        
        document.processing_status = ProcessingStatus.CHUNKING
        db.commit()
        
        # Process text
        process_document(db, document_id, conversation_id, text)
        
        logger.info(f"URL {url} processed successfully.")
        return document_id

    except Exception as e:
        logger.error(f"Failed to process URL {url}: {e}")
        
        if document_id:
            doc = db.query(Document).filter(Document.document_id == document_id).first()
            if doc:
                doc.processing_status = ProcessingStatus.FAILED
                db.commit()
                
        raise HTTPException(status_code=500, detail=f"URL processing failed: {e}")
