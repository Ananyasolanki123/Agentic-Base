import os
import logging
import uuid
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.gemini import Gemini
# from llama_index.llms.groq import Groq
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.agent import ReActAgent
import chromadb
import nest_asyncio

# Patch asyncio to allow nested loops (Critical for LlamaIndex in background threads)
nest_asyncio.apply()

from .Db.models import Base, Repository, RepoStatus
from .tools.git_tool import GitTool
from .tools.fs_tool import FileSystemTool
from .opik_config import configure_opik

logger = logging.getLogger(__name__)

# Database Setup
DB_URL = "sqlite:///src/Agents/RepoDocAgent/Db/repodoc.db"
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# LLM Setup (Gemini)
# GROQ_API_KEY = os.getenv("GROQ_API_KEY") # Commented out
# llm = Groq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)

# Use Gemini for LLM too
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY not found! Gemini LLM will fail.")
else:
    logger.info(f"GOOGLE_API_KEY loaded: {GOOGLE_API_KEY[:5]}...")

llm = Gemini(model="models/gemini-2.0-flash", api_key=GOOGLE_API_KEY)
Settings.llm = llm

# Embedding Setup (Gemini - Paid Key)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY not found! Gemini Embeddings will fail.")
else:
    logger.info(f"GOOGLE_API_KEY loaded: {GOOGLE_API_KEY[:5]}...")

Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001", api_key=GOOGLE_API_KEY)

# Opik Setup
configure_opik()

class RepoDocAgent:
    def __init__(self):
        self.git_tool = GitTool()
        self.fs_tool = FileSystemTool()
        self.chroma_client = chromadb.PersistentClient(path="storage/chroma_db")
        self.chroma_collection = self.chroma_client.get_or_create_collection("repo_docs_gemini")
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # Initialize ReAct Agent directly (Constructor)
        self.agent = ReActAgent(
            tools=[self.git_tool.get_tool()] + self.fs_tool.get_tools(),
            llm=llm,
            verbose=True
        )

    def generate_docs(self, repo_url: str) -> str:
        """
        Orchestrates the documentation generation process.
        """
        db = SessionLocal()
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        
        # 1. Create/Update Repo Record
        repo = db.query(Repository).filter(Repository.url == repo_url).first()
        if not repo:
            repo = Repository(url=repo_url, name=repo_name, status=RepoStatus.PENDING)
            db.add(repo)
            db.commit()
        
        try:
            # 2. Clone Repo
            repo.status = RepoStatus.CLONING
            db.commit()
            
            local_path = self.git_tool.clone_repo(repo_url, repo_name)
            repo.local_path = local_path
            repo.status = RepoStatus.CLONED
            db.commit()
            
            # 3. Generate Docs (Using the Agent to "think" and traverse)
            # For simplicity in this v1, we will instruct the agent to generate a README for the root.
            # In a full implementation, we would iterate recursively.
            
            docs_path = f"storage/docs/{repo_name}"
            repo.docs_path = docs_path
            
            prompt = (
                f"I have cloned a repository at '{local_path}'. The remote URL is '{repo_url}'.\n"
                f"Your task is to generate detailed TECHNICAL documentation for this codebase.\n\n"
                f"**CRITICAL INSTRUCTION: UNIVERSAL LINK CITATION**\n"
                f"When you mention a file, class, or function, you MUST provide a Markdown link to the exact location in the GitHub repository.\n"
                f"Format: `[filename:LineNumber](https://github.com/user/repo/blob/main/path/to/file.py#L10)`\n"
                f"Example: `[src/main.py:L45]({repo_url}/blob/main/src/main.py#L45)`\n"
                f"Ensure the links are valid and point to the correct branch (usually 'main' or 'master').\n\n"
                f"1. Explore the file structure recursively to understand the project layout.\n"
                f"2. Read the actual source code files (e.g., inside 'src/', 'lib/', or root .py/.js files). Do NOT rely solely on the README.\n"
                f"3. Analyze the key classes, functions, and their interactions.\n"
                f"4. Write a comprehensive 'index.md' file to '{docs_path}/index.md' with the following sections:\n"
                f"   - **Project Overview**: High-level summary.\n"
                f"   - **Architecture**: How the components interact.\n"
                f"   - **Key Modules**: Technical breakdown of important files/classes (WITH LINKS).\n"
                f"   - **Setup & Usage**: Inferred from requirements and code.\n"
                f"   - **Future Improvements**: Potential refactoring or features based on code analysis.\n"
            )
            
            # --- ROBUST ASYNC EXECUTION ---
            import asyncio
            
            # 1. Define the async task
            async def _run_agent_async():
                # Check if we need to use 'achat' (async chat) or just 'run'
                if hasattr(self.agent, 'achat'):
                    return await self.agent.achat(prompt)
                elif hasattr(self.agent, 'arun'):
                    return await self.agent.arun(prompt)
                else:
                    # Fallback to sync run if no async method exists, 
                    # but usually LlamaIndex agents have 'achat' or 'arun'
                    return self.agent.run(prompt)

            # 2. Run it in a fresh event loop for this thread
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Execute the agent
                response_obj = loop.run_until_complete(_run_agent_async())
                
                # Check if response_obj is a WorkflowHandler (common in new LlamaIndex versions)
                # If it has a .result() method, we might need to await it or call it.
                # But since we are in sync land now (outside the loop's run_until_complete), 
                # we can't await. We should have awaited it INSIDE _run_agent_async.
                
                # Let's modify _run_agent_async to handle this.
                # But since we can't redefine it easily here without a full rewrite, 
                # let's try to inspect it.
                
                # Actually, if response_obj is a WorkflowHandler, it means the agent started 
                # but didn't finish? No, run_until_complete should wait for the coroutine.
                
                # The issue is likely that self.agent.run() returns a Handler immediately, 
                # and the actual work happens in background tasks that need the loop to stay alive.
                
                # FIX: We need to await the handler's result INSIDE the async function.
                
                async def _run_and_wait():
                    res = await _run_agent_async()
                    
                    # DEBUG: Print type
                    logger.info(f"Agent run returned type: {type(res)}")
                    
                    # If res is a Future/Task (which WorkflowHandler might wrap or behave like),
                    # we should await it directly to get the result.
                    # Calling .result() on a pending Future raises InvalidStateError.
                    if asyncio.isfuture(res) or hasattr(res, "__await__"):
                        return await res
                    
                    # If it has a .result() method but isn't a future (unlikely given the error),
                    # we might need to check if it's done. But the error strongly suggests it's a Future.
                    
                    return res

                final_response = loop.run_until_complete(_run_and_wait())
                response = str(final_response)
                
                loop.close()
            except Exception as inner_e:
                logger.error(f"Async loop execution failed: {inner_e}")
                import traceback
                traceback.print_exc()
                raise inner_e # Re-raise to trigger the outer exception handler properly
            # -----------------------------

            logger.info(f"Agent Response: {response}")
            
            # 4. Index Docs
            repo.status = RepoStatus.INDEXING
            db.commit()
            self._index_docs(docs_path)
            
            repo.status = RepoStatus.COMPLETED
            db.commit()
            
            return f"Documentation generated and indexed for {repo_name}. View at /view/{repo_name}/index.html"

        except Exception as e:
            logger.error(f"Job failed: {e}")
            import traceback
            traceback.print_exc()
            repo.status = RepoStatus.FAILED
            repo.error_message = str(e)
            db.commit()
            return f"Failed to generate docs: {e}"
        finally:
            db.close()

    def _index_docs(self, docs_path: str):
        """
        Indexes the generated markdown files into ChromaDB.
        """
        if not os.path.exists(docs_path):
            logger.warning(f"No docs found at {docs_path} to index.")
            return

        documents = SimpleDirectoryReader(docs_path).load_data()
        if not documents:
            logger.warning("No documents loaded.")
            return
            
        VectorStoreIndex.from_documents(
            documents, storage_context=self.storage_context
        )
        logger.info(f"Indexed {len(documents)} documents from {docs_path}")
