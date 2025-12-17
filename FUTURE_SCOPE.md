# Future Scope & Scalability Roadmap

This document outlines potential improvements and future directions for the "Bot Assignment" project. These points are designed to demonstrate a deep understanding of system design, scalability, and production-readiness during your interview.

## 1. Advanced Vector Database Integration
**Current State:** Uses `pgvector` (implied by SQLAlchemy models) or simple in-memory/database storage for embeddings.
**Future Scope:**
- **Dedicated Vector DB:** Migrate to a specialized vector database like **Qdrant**, **Pinecone**, or **Weaviate**.
- **Why?** These databases offer superior performance for millions of vectors, built-in HNSW indexing for fast approximate nearest neighbor search, and better filtering capabilities.
- **Impact:** Reduces latency for RAG queries and allows scaling to millions of documents.

## 2. Asynchronous Document Processing
**Current State:** Document processing (chunking/embedding) likely happens synchronously or blocks the main thread/request.
**Future Scope:**
- **Task Queue:** Implement **Celery** with **Redis** or **RabbitMQ**.
- **Workflow:** When a user uploads a PDF, the API returns a "Processing" status immediately. The heavy lifting (OCR, chunking, embedding) happens in a background worker.
- **Impact:** Prevents API timeouts during large file uploads and improves user experience.

## 3. Hybrid Search (Semantic + Keyword)
**Current State:** Relies purely on semantic search (cosine similarity of embeddings).
**Future Scope:**
- **BM25 + Dense Vectors:** Combine keyword-based search (BM25) with semantic search (embeddings).
- **Reranking:** Use a Cross-Encoder (like `ms-marco-MiniLM`) to rerank the top 10-20 results from the hybrid search.
- **Impact:** drastically improves retrieval accuracy, especially for specific terms (names, IDs, technical jargon) that semantic search might miss.

## 4. Advanced Context Management
**Current State:** Sliding window or simple token truncation.
**Future Scope:**
- **Context Summarization:** Periodically summarize older parts of the conversation using a cheaper LLM (e.g., Llama-3-8b) to retain long-term memory without hitting token limits.
- **GraphRAG:** Build a knowledge graph from uploaded documents to understand relationships between entities, not just similarity.

## 5. Security & Multi-Tenancy
**Current State:** Basic user ID association.
**Future Scope:**
- **RBAC (Role-Based Access Control):** Admin vs. Regular User roles.
- **Document Level Permissions:** Granular control over which users can "see" or "chat" with specific documents within an organization.
- **PII Redaction:** Automatically detect and redact Personally Identifiable Information (PII) from PDFs before embedding them.

## 6. Observability & Evaluation
**Current State:** Basic logging.
**Future Scope:**
- **LLM Tracing:** Integrate **LangSmith** or **Arize Phoenix** to trace every step of the RAG pipeline (retrieval score, LLM input/output).
- **RAG Evaluation:** Use **Ragas** or **DeepEval** to automatically score answers based on Faithfulness, Answer Relevance, and Context Precision.

## 7. Implementation Guide (Where & How)

This section details exactly where to integrate the code examples from `future_enhancements.py` into your existing codebase.

### A. Implementing Vector Database
**Target File:** `src/Services/rag_service.py`
**Target Function:** `retrieve_context_for_query`

**How to Integrate:**
1.  Replace the current in-memory cosine similarity logic (lines 114-134) with a call to the `VectorStoreService`.
2.  Instead of fetching *all* chunks from the DB and filtering in Python, you will send the query vector to the Vector DB and get back only the relevant chunk IDs.

**Target File:** `src/Db/models.py`
**Target Class:** `DocumentChunk`

**How to Integrate:**
1.  Change `embedding = Column(Text)` to use a specialized vector type if using `pgvector` (e.g., `Vector(384)`), or remove it if using an external DB like Pinecone.

### B. Implementing Async Processing
**Target File:** `src/Services/document_processor.py`
**Target Function:** `process_document_upload`

**How to Integrate:**
1.  Currently, `process_document_upload` (line 101) awaits the entire processing chain.
2.  **Change:** Make this endpoint simply save the file to S3/Local storage and push a message to a queue (e.g., `celery_app.send_task(...)`).
3.  **Worker:** Create a new file `src/worker.py` that consumes these tasks and calls `_generate_and_save_chunks` (line 68).

### C. Implementing Hybrid Search
**Target File:** `src/Services/rag_service.py`
**Target Function:** `retrieve_context_for_query`

**How to Integrate:**
1.  Modify `retrieve_context_for_query` to perform two searches:
    -   **Semantic:** Using `_embedder.encode(query)` (existing logic).
    -   **Keyword:** Using a BM25 library (e.g., `rank_bm25`) on the chunk text.
2.  Combine the results using Reciprocal Rank Fusion (RRF) as shown in `future_enhancements.py` -> `HybridRetriever`.
