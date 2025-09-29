import logging
from app.session_manager import (get_session, update_session, get_chat_history, get_stage, 
                                 set_stage, clear_session_for_global_reset, update_conversation_context)
from .primary_intent_agent import get_primary_intent, Product
from .travel_payload_agent import run_travel_payload_agent
from .family_payload_agent import run_family_payload_agent
from .quote_manager import run_quote_generation

logger = logging.getLogger(__name__)

def orchestrate_chat(user_message: str, session_id: str) -> str:
    """Orchestrator that handles multiple product agents."""
    try:
        if user_message.strip().lower() in ["hi", "hello"]:
            clear_session_for_global_reset(session_id)
            agent_response = "Hello! I can help you with Travel or Family insurance. Which one are you interested in?"
            update_session(session_id, user_message, agent_response)
            return agent_response

        stage = get_stage(session_id)
        chat_history = get_chat_history(session_id)
        
        if not stage or stage == 'initial':
            intent_result = get_primary_intent(user_message, chat_history)
            product = intent_result.product
            intent = intent_result.intent
            agent_response = ""

            # --- NEW LOGIC START: Handle greetings explicitly ---
            if intent == 'greeting':
                agent_response = "Hello! I can help you with Travel or Family insurance. Which one are you interested in?"
            # --- NEW LOGIC END ---

            elif product == Product.TRAVEL:
                set_stage(session_id, 'travel_collection')
                update_conversation_context(session_id, primary_product='TRAVEL')
                response_data = run_travel_payload_agent(user_message, chat_history, session_id)
                agent_response = response_data.get("output")
            elif product == Product.FAMILY:
                set_stage(session_id, 'family_collection')
                update_conversation_context(session_id, primary_product='FAMILY')
                response_data = run_family_payload_agent(user_message, chat_history, session_id)
                agent_response = response_data.get("output")
            else:
                agent_response = "I can help with Travel or Family insurance. Which product are you interested in?"
        
        elif stage == 'travel_collection':
            response_data = run_travel_payload_agent(user_message, chat_history, session_id)
            agent_response = response_data.get("output")
        elif stage == 'family_collection':
            response_data = run_family_payload_agent(user_message, chat_history, session_id)
            agent_response = response_data.get("output")
        elif stage == 'quote_generation':
            response_data = run_quote_generation(session_id)
            agent_response = response_data.get("output")
        else:
            agent_response = "I'm not sure how to help with that. Please start by telling me if you need Travel or Family insurance."

        update_session(session_id, user_message, agent_response)
        return agent_response
        
    except Exception as e:
        logger.error(f"Critical error in orchestrate_chat for session {session_id}: {str(e)}")
        return "I'm sorry, a critical error occurred. Please start over by saying 'hi'."