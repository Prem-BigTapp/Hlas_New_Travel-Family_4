import os
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Now import agents (which may rely on env vars)
from agents.intelligent_orchestrator import orchestrate_chat

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """
    Main endpoint for receiving chat messages for testing.
    """
    logger.info(f"Received message for session: {request.session_id}")
    
    try:
        # Call the orchestrator to get the chatbot's response
        response_message = orchestrate_chat(request.message, request.session_id)
        
        logger.info(f"Sending response for session {request.session_id}: {str(response_message)[:100]}...")
        
        # Return the response in the JSON
        return {"response": response_message}
    
    except Exception as e:
        logger.error(f"Critical error in main chat endpoint: {e}")
        return {"response": "I'm sorry, a critical error occurred. Please try again later."}

@app.get("/")
def root():
    """
    A simple health check endpoint.
    """
    return {"status": "HLAS Bot API is running"}


    