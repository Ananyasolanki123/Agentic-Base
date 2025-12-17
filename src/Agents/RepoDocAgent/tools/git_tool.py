import os
import git
from typing import Optional
from llama_index.core.tools import FunctionTool
import logging

logger = logging.getLogger(__name__)

class GitTool:
    def __init__(self, base_storage_path: str = "storage/repos"):
        self.base_storage_path = base_storage_path
        os.makedirs(self.base_storage_path, exist_ok=True)

    def clone_repo(self, repo_url: str, repo_name: str) -> str:
        """
        Clones a GitHub repository to the local storage.
        Returns the path to the cloned repository.
        """
        target_path = os.path.join(self.base_storage_path, repo_name)
        
        if os.path.exists(target_path):
            logger.info(f"Repo {repo_name} already exists at {target_path}. Pulling latest changes.")
            try:
                repo = git.Repo(target_path)
                repo.remotes.origin.pull()
                return target_path
            except Exception as e:
                logger.error(f"Failed to pull repo: {e}")
                # Fallback: return path anyway, assuming it's usable
                return target_path
        
        try:
            logger.info(f"Cloning {repo_url} to {target_path}")
            git.Repo.clone_from(repo_url, target_path)
            return target_path
        except Exception as e:
            logger.error(f"Failed to clone repo: {e}")
            raise e

    def get_tool(self):
        return FunctionTool.from_defaults(
            fn=self.clone_repo,
            name="clone_repository",
            description="Clones a GitHub repository given its URL and a name. Returns the local path."
        )
