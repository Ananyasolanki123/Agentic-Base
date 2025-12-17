from sqlalchemy import Column, String, Enum, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()

class RepoStatus(enum.Enum):
    PENDING = "PENDING"
    CLONING = "CLONING"
    CLONED = "CLONED"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    
    # Paths on disk
    local_path = Column(String, nullable=True) # Where source code is cloned
    docs_path = Column(String, nullable=True)  # Where generated docs are saved
    
    status = Column(Enum(RepoStatus), default=RepoStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
