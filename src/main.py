
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
import warnings

# Suppress Pydantic V2 warnings from LlamaIndex/Opik
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from src.api.router import router as conversation_router
from src.Agents.ChatBot.Db.__init__ import create_db_tables, get_db
from src.Agents.ChatBot.Db import models 

# Import RepoDoc Agent Router
from src.Agents.RepoDocAgent.interface.api import router as repodoc_router

app = FastAPI(
    title="BOT GPT Backend", 
    version="v1.0.0"
)

# Mount Routers
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(repodoc_router, prefix="/api/v1")

# Mount Static Files for Documentation Viewing
DOCS_DIR = "storage/docs"
os.makedirs(DOCS_DIR, exist_ok=True)
app.mount("/view", StaticFiles(directory=DOCS_DIR, html=True), name="docs")
