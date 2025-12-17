import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from groq import Groq, APIError
from fastapi import HTTPException, status
from dotenv import load_dotenv
from opik import track

from ..Db.models import Message, MessageRole 

load_dotenv()

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
LLM_MODEL = "llama-3.1-8b-instant" 
MAX_MODEL_TOKENS = 32768 # Updated context window size for Mixtral
SAFETY_THRESHOLD = 0.8  
CONTEXT_LIMIT = int(MAX_MODEL_TOKENS * SAFETY_THRESHOLD) # Calculation updated: 26214 tokens
SYSTEM_PROMPT = (
    "You are BOT GPT, a helpful and concise enterprise conversational assistant. "
    "Your goal is to answer user queries based on conversation history and provided documents. "
    "You must return your response in valid JSON format with the following structure: "
    "{\"answer\": \"your answer here\", \"citations\": [{\"source\": \"source url or name\", \"snippet\": \"relevant text snippet\"}]}. "
    "Be professional and brief."
)
# ---------------------

# Initialize the Groq client
try:
    client = Groq() 
except Exception as e:
    client = None
    logger.error(f"Failed to initialize Groq Client: {e}. Check your GROQ_API_KEY.")


def count_tokens(text: str) -> int:
    
    if not text:
        return 0
    return len(text) // 4

def format_messages_for_llm(
    conversation_history: List[Message], 
    rag_context: Optional[Any] = None
) -> List[Dict[str, str]]:
   
    formatted_messages = []
    
    full_system_prompt = SYSTEM_PROMPT
    if rag_context:
        # Convert structured context to string for prompt
        context_str = ""
        if isinstance(rag_context, list):
            for item in rag_context:
                context_str += f"Source: {item['source']}\nContent: {item['content']}\n\n"
        else:
            context_str = str(rag_context)

        full_system_prompt = (
            f"RAG CONTEXT:\n---\n{context_str}\n---\n\n"
            f"{SYSTEM_PROMPT}"
        )
        
    formatted_messages.append({"role": "system", "content": full_system_prompt})

    for message in conversation_history:
        role_str = message.role.value.lower() 
        formatted_messages.append({
            "role": role_str, 
            "content": message.content
        })

    return formatted_messages


def manage_context_window(
    conversation_history: List[Message], 
    rag_context: Optional[Any] = None
) -> List[Message]:
    
    
    base_prompt = SYSTEM_PROMPT
    base_tokens = count_tokens(base_prompt)
    if rag_context:
        context_str = ""
        if isinstance(rag_context, list):
            for item in rag_context:
                context_str += f"Source: {item['source']}\nContent: {item['content']}\n\n"
        else:
            context_str = str(rag_context)
        base_tokens += count_tokens(context_str)
    
    
    current_tokens = base_tokens
    processed_history: List[Message] = []
    
    for message in reversed(conversation_history):
        message_tokens = count_tokens(message.content)
        
        if current_tokens + message_tokens <= CONTEXT_LIMIT:
            current_tokens += message_tokens
          
            processed_history.insert(0, message)
        else:
            logger.warning(
                f"Context window hit limit ({CONTEXT_LIMIT} tokens). "
                f"Discarding message sequence #{message.sequence_number}."
            )
            break
            
    return processed_history

# ---------------------

@track(name="chat_bot_llm_call")
async def call_llm_api(conversation_history: List[Message], rag_context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Orchestrates context management and calls the Groq API.
    """
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Groq Client is not initialized. Check server logs for API key errors."
        )

   
    processed_history = manage_context_window(conversation_history, rag_context)
    
    messages_payload = format_messages_for_llm(processed_history, rag_context)

    
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages_payload,
                temperature=0,
                response_format={"type": "json_object"}
            )

            if response.choices:
                content = response.choices[0].message.content
                
                total_tokens = response.usage.total_tokens if response.usage else 0
                
                return {
                    'content': content,
                    'model': LLM_MODEL,
                    'token_usage': total_tokens
                }
            else:
                raise Exception("Groq returned an empty response candidate list.")
        
        except APIError as e:
            logger.error(f"Groq API Error (Status {e.status_code}) on attempt {attempt + 1}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="External Groq service is unavailable after multiple retries."
                )
        
        except Exception as e:
            logger.error(f"General LLM API Call failed on attempt {attempt + 1}: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="External Groq service failed due to an unknown error."
            )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="LLM service failed after all retries."
    )