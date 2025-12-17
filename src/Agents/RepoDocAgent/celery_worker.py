from dotenv import load_dotenv
import os
import logging

# Load environment variables FIRST
load_dotenv()

from celery import Celery
from .agent import RepoDocAgent

# Initialize Logger
logger = logging.getLogger(__name__)

# CloudAMQP URL (Get from .env or use default local)
BROKER_URL = os.getenv("CLOUDAMQP_URL", "amqp://guest:guest@localhost:5672//")

celery_app = Celery(
    "repodoc_worker",
    broker=BROKER_URL,
    backend="rpc://" # Use RPC for result backend or configure Redis if needed
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="src.Agents.RepoDocAgent.celery_worker.generate_docs_task")
def generate_docs_task(self, repo_url: str):
    """
    Celery task to generate documentation.
    """
    logger.info(f"Received task for {repo_url}")
    try:
        # Initialize Agent inside the worker process
        agent = RepoDocAgent()
        result = agent.generate_docs(repo_url)
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise e
