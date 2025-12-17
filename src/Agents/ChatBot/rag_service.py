from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
import uuid
import logging
from .Db.models import Document, ConvDocumentLink, Conversation, ProcessingStatus
import torch
import ast 
from .Db.models import  DocumentChunk
from sentence_transformers import SentenceTransformer, util
from sqlalchemy.exc import SQLAlchemyError 

logger = logging.getLogger(__name__)


def create_document_and_link(db: Session, user_id: str, filename: str) -> Document:
    
    new_doc_id = str(uuid.uuid4())
    
    new_document = Document(
        document_id=new_doc_id,
        user_id=user_id,
        filename=filename,
        storage_path=f"s3://bot-docs/{new_doc_id}",
        processing_status='READY'
    )
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    
    return new_document


def link_documents_to_conversation(db: Session, conversation_id: str, document_ids: list):
   
    # 1. Convert single string to list
    if isinstance(document_ids, str):
        document_ids = [document_ids]

    successful_links = []
    
    # 2. Iterate and add links to the session
    for doc_id in document_ids:
        doc = db.query(Document).filter(Document.document_id == doc_id).first()
        if not doc or doc.processing_status != ProcessingStatus.READY:
            logger.warning(
                f"Document ID {doc_id} not found or not READY. Skipping link for conversation {conversation_id}."
            )
            continue

        try:
            link = ConvDocumentLink(
                conversation_id=conversation_id,
                document_id=doc_id
            )
            db.add(link)
            successful_links.append(doc_id)
        except Exception as e:
            # This handles errors during object creation/session add, though less common here
            logger.error(
                f"Error adding link for doc {doc_id} to session. Details: {e}", exc_info=True
            )
            # Do not continue to commit if the session is broken by an unhandled error here
            return 

    # 3. Attempt to commit all successful links
    if successful_links:
        try:
            db.commit()
            logger.info(
                f"Successfully linked documents {successful_links} to conversation {conversation_id}."
            )
        except SQLAlchemyError as e:
            # CRITICAL: Rollback if the commit fails (e.g., Foreign Key violation, network error)
            db.rollback() 
            logger.error(
                f"DB commit failed while linking documents {successful_links} to conversation {conversation_id}. Error: {e}", 
                exc_info=True
            )
            # Re-raise the exception to inform the calling function (the FastAPI router)
            raise


# Load embedding model lazily
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def retrieve_context_for_query(db: Session, conversation, user_query: str) -> Optional[List[Dict[str, Any]]]:
    
    # 1) Get linked documents (UNCHANGED)
    links = db.query( ConvDocumentLink).filter(
        ConvDocumentLink.conversation_id == conversation.conversation_id
    ).all()

    if not links:
        return None

    document_ids = [row.document_id for row in links]

    # 2) Fetch all chunks belonging to those documents
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(document_ids)
    ).all()

    if not chunks:
        return None

    # 3) Encode query and score against chunks 
    # The output is a 2D tensor: [1, embedding_dim]
    embedder = get_embedder()
    query_emb = embedder.encode(user_query, convert_to_tensor=True).unsqueeze(0)

    scored = []
    for chunk in chunks:
        try:
            # Safely parse the string representation back into a Python list of floats
            embedding_list = ast.literal_eval(chunk.embedding)
            
            #  Create tensor from the LIST, then convert to 2D tensor [1, embedding_dim]
            chunk_emb_2d = torch.tensor(embedding_list, dtype=torch.float32).unsqueeze(0) 
            
        except (ValueError, SyntaxError, TypeError) as e:
            logger.error(f"Failed to decode or convert embedding for chunk {chunk.chunk_id}: {e}. Skipping chunk.")
            continue 
        
        score = util.pytorch_cos_sim(query_emb, chunk_emb_2d).item()
        scored.append((score, chunk.content, chunk.document_id))

    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Return structured context
    structured_context = []
    for _, text, doc_id in scored[:5]:
        doc = db.query(Document).filter(Document.document_id == doc_id).first()
        source = doc.storage_path if doc else "Unknown Source"
        structured_context.append({
            "content": text,
            "source": source
        })

    return structured_context if structured_context else None

def get_documents_for_conversation(db: Session, conversation_id: str):
  
    links = db.query(ConvDocumentLink).filter(
        ConvDocumentLink.conversation_id == conversation_id
    ).all()

    if not links:
        return []

    document_ids = [link.document_id for link in links]

    documents = db.query(Document).filter(Document.document_id.in_(document_ids)).all()
    return documents

def delete_documents_for_conversation(db: Session, conversation_id: str):
   
    linked_docs = db.query(ConvDocumentLink).filter(
        ConvDocumentLink.conversation_id == conversation_id
    ).all()
    
    document_ids = [link.document_id for link in linked_docs]

    db.query(ConvDocumentLink).filter(
        ConvDocumentLink.conversation_id == conversation_id
    ).delete(synchronize_session=False)

    for doc_id in document_ids:
        other_links = db.query(ConvDocumentLink).filter(
            ConvDocumentLink.document_id == doc_id
        ).count()
        
        if other_links == 0:
            db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).delete(synchronize_session=False)
            db.query(Document).filter(Document.document_id == doc_id).delete(synchronize_session=False)

    db.commit()