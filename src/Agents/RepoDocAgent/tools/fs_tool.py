import os
from typing import List, Dict
from llama_index.core.tools import FunctionTool
import logging

logger = logging.getLogger(__name__)

class FileSystemTool:
    def __init__(self):
        pass

    def list_files(self, directory_path: str, recursive: bool = True) -> List[str]:
        """
        Lists all files in a directory.
        Ignores .git, __pycache__, node_modules, etc.
        """
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', '.idea', '.vscode'}
        file_list = []
        
        for root, dirs, files in os.walk(directory_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.startswith('.'): # Ignore hidden files
                    continue
                file_list.append(os.path.join(root, file))
                
            if not recursive:
                break
                
        return file_list

    def read_file(self, file_path: str) -> str:
        """
        Reads the content of a file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            return "<Binary File or Non-UTF8 Content>"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def write_doc(self, content: str, output_path: str):
        """
        Writes documentation content to a file.
        Ensures directories exist.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {output_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool.from_defaults(fn=self.list_files, name="list_files", description="Lists all files in a directory recursively."),
            FunctionTool.from_defaults(fn=self.read_file, name="read_file", description="Reads the content of a file."),
            FunctionTool.from_defaults(fn=self.write_doc, name="write_documentation", description="Writes markdown documentation to a specific file path.")
        ]
