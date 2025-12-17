import os
import logging
from opik import Opik
from opik.integrations.llama_index import LlamaIndexCallbackHandler
from llama_index.core import Settings

logger = logging.getLogger(__name__)

def configure_opik():
    """
    Configures Opik tracing for LlamaIndex.
    """
    try:
        # Check for API Key
        if not os.getenv("OPIK_API_KEY"):
            logger.warning("OPIK_API_KEY not found. Tracing will be disabled.")
            return None

        # Initialize Opik Client
        client = Opik(project_name="Bot-Assignment-Agentic")
        
        # Create Callback Handler - It automatically uses the global project if configured, 
        # or we can try passing project_name if supported, but let's stick to no-args for now 
        # as the error said 'opik_client' was unexpected.
        opik_callback = LlamaIndexCallbackHandler()
        
        # Add to LlamaIndex Settings
        Settings.callback_manager.add_handler(opik_callback)
        
        logger.info("Opik tracing configured successfully.")
        return client
    except Exception as e:
        logger.warning(f"Failed to configure Opik: {e}. Tracing will be disabled.")
        return None
