import requests
import json
import logging

logger = logging.getLogger(__name__)

class RepoDocTool:
    def __init__(self, acp_endpoint: str = "http://localhost:8000/api/v1/agents/repodoc/acp"):
        self.acp_endpoint = acp_endpoint

    def generate_docs(self, repo_url: str) -> str:
        """
        Triggers the RepoDoc Agent to generate documentation for a GitHub repository.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "generate_docs",
            "params": {"repo_url": repo_url},
            "id": "1"
        }
        
        try:
            response = requests.post(self.acp_endpoint, json=payload, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                return f"Error from RepoDoc Agent: {data['error']['message']}"
            
            result = data.get("result", {})
            return f"Documentation generation started. Job ID: {result.get('job_id')}. You will be notified when it's done."
            
        except Exception as e:
            logger.error(f"Failed to call RepoDoc Agent: {e}")
            return f"Failed to communicate with RepoDoc Agent: {e}"
