from sqlalchemy.orm import Session
from sqlalchemy import select
import uuid
from typing import List, Optional, Tuple, Dict, Any 
import logging
from fastapi import HTTPException 

from .Db.models import User, Conversation, Message, MessageRole, ConversationMode 
from .rag_service import create_document_and_link
from .Db.models import ConvDocumentLink, Document, DocumentChunk

from .LLM.llm_client import call_llm_api
from .rag_service import get_documents_for_conversation
from .rag_service import link_documents_to_conversation, retrieve_context_for_query
logger = logging.getLogger(__name__)


def _get_next_sequence_number(db: Session, conversation_id: str) -> int:
    max_seq = db.query(Message.sequence_number).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_number.desc()).first()
    
    return (max_seq[0] + 1) if max_seq else 1


def create_initial_conversation(
    db: Session, 
    user_id: str, 
    first_message_content: str, 
    mode: str,
    document_ids: List[str] = None 
) -> Tuple[Optional[Conversation], Optional[Message]]:
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, email=f"{user_id}@botgpt.com")
        db.add(user)
        db.flush()
        
    new_conversation = Conversation(
        conversation_id=str(uuid.uuid4()),
        user_id=user_id,
        mode=mode
    )
    db.add(new_conversation)
    db.flush()
    
    if mode == ConversationMode.RAG_CHAT.value and document_ids:
        link_documents_to_conversation(
            db=db, 
            conversation_id=new_conversation.conversation_id, 
            document_ids=document_ids
        )
       
    user_message = Message(
        message_id=str(uuid.uuid4()),
        sequence_number=1,
        role=MessageRole.USER,
        content=first_message_content
    )
    new_conversation.messages.append(user_message)
    
    db.commit()
    db.refresh(new_conversation)
    db.refresh(user_message) 

    return new_conversation,user_message

def get_conversations_list(db: Session, user_id: str) -> List[Conversation]:
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.last_updated_at.desc()).all()
    
    return conversations

def get_conversation_detail(db: Session, conversation_id: str) -> Optional[Conversation]:
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()
    return conversation

def delete_conversation(db: Session, conversation_id: str):
    result = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).delete(synchronize_session=False) 
    
    db.commit()
    return result > 0

def add_user_message(db: Session, conversation_id: str, content: str) -> Optional[Message]:
    
    next_seq = _get_next_sequence_number(db, conversation_id)
    
    user_message = Message(
        message_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sequence_number=next_seq,
        role=MessageRole.USER,
        content=content
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    return user_message


async def process_user_message_and_get_reply(
    db: Session, 
    conversation_id: str,
    user_message_content: str,
    rag_context: Optional[Any] = None

) -> Optional[Message]:
   

    conversation = get_conversation_detail(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    user_message = add_user_message(db, conversation_id, user_message_content)
    db.refresh(conversation)  

    rag_context = None
    linked_docs = []
    if conversation.mode == ConversationMode.RAG_CHAT:
        linked_docs = get_documents_for_conversation(db, conversation.conversation_id)
        
        if not linked_docs:
            logger.warning(f"No documents linked to conversation {conversation.conversation_id}")
        
        rag_context = retrieve_context_for_query(
            db=db,
            conversation=conversation,
            user_query=user_message_content
        )

        if not rag_context:
            logger.warning(f"RAG context empty for conversation {conversation.conversation_id}")
        else:
            logger.info(f"RAG context retrieved ({len(linked_docs)} docs)")

    history = conversation.messages

    llm_result = await call_llm_api(history, rag_context)

    next_seq = _get_next_sequence_number(db, conversation_id)
    assistant_message = Message(
        message_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sequence_number=next_seq,
        role=MessageRole.ASSISTANT,
        content=llm_result['content'],
        llm_model=llm_result['model']
    )
    db.add(assistant_message)

    conversation.token_count += llm_result.get('token_usage', 0)

    db.commit()
    db.refresh(assistant_message)

    return assistant_message





def add_assistant_message_mock(db: Session, conversation_id: str, content: str) -> Optional[Message]:
    max_seq = db.query(Message.sequence_number).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.sequence_number.desc()).first()
    next_seq = (max_seq[0] + 1) if max_seq else 1
    
    assistant_message = Message(
        message_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        sequence_number=next_seq,
        role=MessageRole.ASSISTANT,
        content=content,
        llm_model="MOCK-GPT"
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    return assistant_message