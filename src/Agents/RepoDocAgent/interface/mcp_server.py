from mcp.server.fastapi import FastAPIServer
from mcp.types import Tool, TextContent, EmbeddedResource
from ..tools.git_tool import GitTool
from ..tools.fs_tool import FileSystemTool

# Initialize Tools
git_tool = GitTool()
fs_tool = FileSystemTool()

# Create MCP Server
mcp = FastAPIServer("RepoDocAgent")

@mcp.tool()
def clone_repository(repo_url: str, repo_name: str) -> str:
    """Clones a GitHub repository."""
    return git_tool.clone_repo(repo_url, repo_name)

@mcp.tool()
def list_files(directory_path: str) -> str:
    """Lists files in a directory."""
    files = fs_tool.list_files(directory_path)
    return "\n".join(files)

@mcp.tool()
def read_file(file_path: str) -> str:
    """Reads a file content."""
    return fs_tool.read_file(file_path)

# The MCP server can be mounted in the main FastAPI app
