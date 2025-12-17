from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import uuid
import sys
from dotenv import load_dotenv

load_dotenv()

def debug_print(msg):
    sys.stdout.write(f"{msg}\n")
    sys.stdout.flush()

# ... (previous imports)
from ..agent import RepoDocAgent, SessionLocal
from ..Db.models import Repository

# Initialize Logger
logger = logging.getLogger(__name__)

# Setup File Logging
file_handler = logging.FileHandler("repodoc.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# Define Router
router = APIRouter(
    prefix="/agents/repodoc",
    tags=["RepoDoc Agent"]
)

def debug_print(msg):
    sys.stdout.write(f"{msg}\n")
    sys.stdout.flush()
    logger.info(msg) # Also write to file

@router.get("/status")
def get_repo_status(repo_url: str):
    """
    Check the status of a repository documentation job.
    """
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.url == repo_url).first()
        if not repo:
            return {"status": "not_found", "repo_url": repo_url}
        
        return {
            "status": repo.status.value,
            "repo_url": repo.url,
            "error": repo.error_message,
            "docs_url": f"/view/{repo.name}/index.html" if repo.status.value == "COMPLETED" else None
        }
    finally:
        db.close()

import traceback

# Initialize Agent (Singleton for now)
try:
    agent_instance = RepoDocAgent()
except Exception as e:
    logger.error(f"Failed to initialize RepoDocAgent: {e}")
    logger.error(traceback.format_exc())
    agent_instance = None

class ACPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any]
    id: Optional[str] = None

class ACPResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

def run_agent_job(repo_url: str, job_id: str):
    """
    Background task to run the agent.
    """
    debug_print(f"--- [DEBUG] Starting job {job_id} for {repo_url} ---")
    logger.info(f"Starting job {job_id} for {repo_url}")
    
    if agent_instance:
        try:
            result = agent_instance.generate_docs(repo_url)
            debug_print(f"--- [DEBUG] Job {job_id} completed: {result} ---")
            logger.info(f"Job {job_id} completed: {result}")
        except Exception as e:
            debug_print(f"--- [DEBUG] Job {job_id} FAILED: {e} ---")
            logger.error(f"Job {job_id} failed: {e}")
            traceback.print_exc()
    else:
        debug_print("--- [DEBUG] Agent instance not available. ---")
        logger.error("Agent instance not available.")

# ... (imports)
from ..celery_worker import generate_docs_task

# ... (rest of imports)

@router.post("/acp", response_model=ACPResponse)
async def handle_acp_message(request: ACPRequest): # Removed BackgroundTasks dependency
    """
    Handles JSON-RPC messages from other agents (ACP).
    """
    debug_print(f"--- [DEBUG] Received ACP request: {request.method} ---")
    
    if request.method == "generate_docs":
        repo_url = request.params.get("repo_url")
        debug_print(f"--- [DEBUG] Repo URL: {repo_url} ---")
        
        if not repo_url:
            return ACPResponse(
                id=request.id,
                error={"code": -32602, "message": "Missing 'repo_url' parameter"}
            )
        
        # Dispatch to Celery
        debug_print(f"--- [DEBUG] Dispatching to Celery ---")
        task = generate_docs_task.delay(repo_url)
        job_id = task.id
        
        return ACPResponse(
            id=request.id,
            result={"status": "queued", "job_id": job_id, "message": "Documentation generation started via Celery."}
        )
    
    return ACPResponse(
        id=request.id,
        error={"code": -32601, "message": "Method not found"}
    )

@router.get("/health")
def health_check():
    return {"status": "active", "agent": "RepoDocAgent"}
