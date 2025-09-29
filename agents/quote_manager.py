import logging
import json
import httpx
import os
from datetime import datetime
from app.session_manager import get_session, set_stage, get_collected_info

logger = logging.getLogger(__name__)

API_ENDPOINTS = {
    "TRAVEL": "/api/v2/quotation/generate",
    "FAMILY": "/api/quotation/generate"
}
API_BASE_URL = os.getenv("API_BASE_URL", "https://api-sandbox.hlas.com.sg")
TEST_MODE = os.getenv("TEST_MODE", "True").lower() == "false"

def _call_api(product: str, payload: dict) -> dict:
    if TEST_MODE:
        logger.warning(f"--- MOCK API CALL for {product} ---")
        if product == "FAMILY":
            return {"success": "ok", "data": {"premiums": [{"productPlan": "bronze", "monthly_premium": "7.77"}]}}
        else: # TRAVEL
            return {"success": "true", "data": {"premiums": {"basic": {"discounted_premium": 21.00}}}}

    endpoint = API_ENDPOINTS.get(product)
    if not endpoint:
        return {"success": "false", "errors": [f"Invalid product '{product}' for quote generation."]}

    url = f"{API_BASE_URL}{endpoint}"
    logger.info(f"--- Calling REAL API for {product}: {url} ---")
    
    try:
        with httpx.Client(timeout=30.0) as client: # Increased timeout
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Error calling {product} quote API: {e}")
        return {"success": "false", "errors": [str(e)]}

def run_quote_generation(session_id: str) -> dict:
    """
    Retrieves the final payload, calls the appropriate API, and returns the full JSON response.
    """
    try:
        session = get_session(session_id)
        context = session.get("conversation_context", {})
        product = context.get("primary_product")
        
        if not product:
            return {"output": "I'm sorry, I've lost track of which product we were discussing."}

        collected_info = get_collected_info(session_id)
        payload_key = "family_payload" if product == "FAMILY" else "payload"
        final_payload = collected_info.get(payload_key)

        if not final_payload:
            return {"output": "I seem to have lost your details. Let's start over."}

        # Call the API to get the quote
        quote_response = _call_api(product, final_payload)
        
        # --- NEW SIMPLIFIED LOGIC ---
        # We no longer parse the response. We just return the whole thing.
        
        if quote_response.get("success") not in ["ok", "true"]:
            logger.error(f"API call for {product} failed. Response: {quote_response}")
        
        set_stage(session_id, "initial") # Reset for the next conversation
        
        # Return the entire raw JSON response from the API as the output
        return {"output": quote_response}
        # --- END OF NEW LOGIC ---

    except Exception as e:
        logger.error(f"Error in run_quote_generation for session {session_id}: {str(e)}")
        set_stage(session_id, "initial")
        return {"output": {"success": "false", "errors": ["A critical error occurred while generating your quote."] } }