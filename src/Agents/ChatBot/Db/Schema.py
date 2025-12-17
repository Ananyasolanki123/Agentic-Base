from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


from .models import MessageRole, ConversationMode 

# ---------------------------------------------
# 1. Message Schemas 
# ---------------------------------------------

class MessageBase(BaseModel):
    """Base structure for data contained in a message object."""
    content: str
    role: MessageRole # Uses the Enum from models.py

class MessageResponse(MessageBase):
    """Schema for returning a message in API responses (includes DB metadata)."""
    message_id: str
    sequence_number: int
    created_at: datetime
    llm_model: Optional[str] = None # Bonus field

    class Config:
       
        from_attributes = True 

# ---------------------------------------------
# 2. Conversation Schemas 
# ---------------------------------------------

class ConversationCreate(BaseModel):
    """Input payload for POST /conversations (Starting a new chat)."""
    first_message: str = Field(..., min_length=1, description="The user's initial message.")
    
    mode: ConversationMode = ConversationMode.OPEN_CHAT
    
    document_ids: List[str] = Field(default_factory=list, description="List of Document IDs to ground the conversation.")

class ConversationContinue(BaseModel):
    """Input payload for POST /conversations/{id}/messages (Continuing a chat)."""
    user_message: str = Field(..., min_length=1, description="The user's subsequent message.")

# ---------------------------------------------
# 3. Conversation List Response
# ---------------------------------------------
class ConversationListResponse(BaseModel):
    """Schema for list items in GET /conversations."""
    conversation_id: str
    title: str
    last_updated_at: datetime
    
    class Config:
        from_attributes = True

class ConversationResponse(ConversationListResponse):
    """Schema for detailed conversation view (includes messages)."""
    mode: ConversationMode
    token_count: int
    
    messages: List[MessageResponse] = [] 
    
    class Config:
        from_attributes = True

class UrlRequest(BaseModel):
    url: str = Field(..., description="The URL of the web page or document to process.")