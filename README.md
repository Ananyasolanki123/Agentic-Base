# Agentic Base

A unified enterprise AI backend built with **FastAPI**, designed to deliver powerful conversational experiences and autonomous code documentation capabilities. This system integrates state-of-the-art LLMs (Groq Llama 3, Google Gemini) and RAG (Retrieval-Augmented Generation) pipelines.

## 🚀 Key Features

### 1. 💬 Enterprise ChatBot
-   **High-Speed Conversations**: Powered by **Groq (Llama 3)** for near-instant responses.
-   **RAG-Enabled**: Upload PDF documents and chat with them using context-aware retrieval.
-   **Intelligent Memory**: Sliding window context management to handle long conversations within token limits.
-   **Conversation Management**: Full CRUD operations for chat sessions and message history.

### 2. 🤖 RepoDoc Agent (New!)
-   **Autonomous Documentation**: An intelligent agent that clones GitHub repositories and generates technical documentation automatically.
-   **Code understanding**: Uses **Google Gemini 2.0 Flash** and **LlamaIndex** to analyze code structure, classes, and logic.
-   **Smart Linking**: Generates "Universal Links" pointing to specific lines of code in the GitHub repo for easy reference.
-   **Vector Search**: Indexes generated documentation into **ChromaDB** for semantic search.

### 3. ⚙️ Robust Architecture
-   **Asynchronous Processing**: Uses **Celery** (with Redis) for handling heavy background tasks like document processing and repo cloning.
-   **Observability**: Integrated with **Opik** for full tracing of LLM inputs, outputs, and RAG retrieval scores.
-   **Agent Protocols**:
    -   **MCP (Model Context Protocol)**: Exposes tools like filesystem access and git cloning for external LLM clients.
    -   **ACP (Agent Communication Protocol)**: Internal JSON-RPC 2.0 standard for agents to communicate with each other.
-   **Scalable Storage**: **PostgreSQL** for relational data and **ChromaDB** for vector embeddings.

---

## 🛠️ Tech Stack

-   **Framework**: FastAPI (Python 3.12+)
-   **Database**: PostgreSQL (Relational), ChromaDB (Vector), Redis (Queue)
-   **LLMs**:
    -   **Chat**: Groq API (Llama 3.3 70B Versatile)
    -   **Agent**: Google Gemini API (Gemini 2.0 Flash)
-   **Embeddings**:
    -   `sentence-transformers/all-MiniLM-L6-v2` (Local/CPU)
    -   Google Gemini Embeddings (`models/embedding-001`)
-   **Orchestration**: LlamaIndex, Docker, Celery

---

## 📋 Prerequisites

-   **Python 3.12+**
-   **PostgreSQL** (running locally or in Docker)
-   **Redis** (for Celery background tasks)
-   **API Keys**:
    -   `GROQ_API_KEY`: For the main ChatBot.
    -   `GOOGLE_API_KEY`: For the RepoDoc Agent and Embeddings.
    -   `OPIK_API_KEY` (Optional): For observability and tracing.

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Environment Configuration

Create a `.env` file in the root directory. You can copy the structure below:

```env
# Database Configuration
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# AI Model Keys
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...

# Optional: Observability
OPIK_API_KEY=...
OPIK_WORKSPACE=...
```

### 3. Install Dependencies

It is recommended to use a virtual environment.

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirement.txt
```

### 4. Run the Application

Start the FastAPI server:

```bash
uvicorn src.main:app --reload
```
The API will be available at `http://localhost:8000`.

---

## 📖 API Documentation

The backend provides a fully interactive Swagger UI.

1.  Start the server.
2.  Navigate to: `http://localhost:8000/docs`

### Core Endpoints

#### 🗣️ Conversations
-   `POST /api/v1/conversations/`: Start a new chat.
-   `POST /api/v1/conversations/{id}/messages`: Send a message (Text or PDF RAG).

#### 📄 RepoDoc Agent
-   `POST /api/v1/repodoc/generate`: Trigger the agent to document a GitHub repo.
-   `POST /api/v1/agents/repodoc/acp`: JSON-RPC endpoint for inter-agent communication.
-   `GET /view/{repo_name}/index.html`: View the generated documentation.

---

## 🔮 Future Scope

We have a clear roadmap for scaling this project, including migrating to dedicated vector databases (Qdrant), implementing hybrid search (BM25 + Semantic), and adding multi-tenancy.

👉 **[Read the full Future Scope & Roadmap](./FUTURE_SCOPE.md)**

---

## 📂 Project Structure

```
.
├── src/
│   ├── Agents/
│   │   ├── ChatBot/        # RAG ChatBot Logic
│   │   └── RepoDocAgent/   # Auto-Documentation Agent
│   ├── api/                # Global API Router
│   ├── Db/                 # Database Models
│   └── main.py             # App Entry Point
├── storage/                # Local storage for docs/vectors
├── FUTURE_SCOPE.md         # Scalability Roadmap
├── requirement.txt         # Dependencies
└── README.md               # You are here
```
