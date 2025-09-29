import logging
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.session_manager import get_session, set_collected_info, set_stage, update_conversation_context

logger = logging.getLogger(__name__)

# --- Payload Template ---
def get_family_payload_template() -> dict:
    """Returns the base payload for Family Protect policies."""
    return {
        "product_code": "FAC",
        "policyInceptionDate": None,
        "mediaWCC": "HLS",
        "IsCEPCustomer": False,
        "IsCEPFirstTimeCustomer": False,
        "hasRider": True,
        "premiumType": None,
        "promoCode": None,
        "CEPReferralCode": None,
        "withChildren": False,
        "withSpouse": False,
        "_internal": { "email": None, "contact_mobile": None, "insured_party": None }
    }

# --- Question Definitions ---
QUESTION_MAP = {
    'premiumType': "Are you looking for a **Monthly** or an **Annual** family insurance plan?",
    'insured_party': "Who is this plan for? (**Myself**, **Myself with Child(ren)**, or **Family**)",
    'policyInceptionDate': "What date would you like the plan to start? (YYYY-MM-DD)",
    'email': "What is your email address?",
    'contact_mobile': "And your 8-digit Singapore mobile number?",
    'promoCode': "Finally, do you have a promocode? (If not, just say 'no')",
}

# --- Main Agent Logic ---
def run_family_payload_agent(user_message: str, chat_history: list, session_id: str) -> dict:
    """Drives the conversation to fill the Family Protect payload."""
    session = get_session(session_id)
    context = session.get("conversation_context", {})
    payload = session.get("collected_info", {}).get("family_payload")

    if not context.get('current_question_key'):
        context['current_question_key'] = 'premiumType'
        payload = get_family_payload_template()
    
    payload, context, validation_error = process_user_answer(user_message, payload, context)
    if validation_error:
        return {"output": validation_error}

    next_question_key = determine_next_question(payload)
    
    if next_question_key == "DONE":
        payload = finalize_payload(payload)
        logger.info("--- FINAL FAMILY PROTECT PAYLOAD ---")
        logger.info(json.dumps(payload, indent=4))
        logger.info("--- END OF PAYLOAD ---")
        
        set_collected_info(session_id, "family_payload", payload)
        set_stage(session_id, "quote_generation")
        update_conversation_context(session_id, current_question_key=None)
        return {"output": "Thank you. Let me get the price for you..."}
    else:
        question_text = QUESTION_MAP[next_question_key]
        update_conversation_context(session_id, current_question_key=next_question_key)
        set_collected_info(session_id, "family_payload", payload)
        return {"output": question_text}

def process_user_answer(user_message: str, payload: dict, context: dict) -> Tuple[dict, dict, Optional[str]]:
    """Updates the payload based on the user's answer."""
    last_q = context.get('current_question_key')
    answer = user_message.strip().lower()
    validation_error = None

    if last_q == 'premiumType':
        payload['premiumType'] = 'annual' if 'annual' in answer else 'monthly'
    
    elif last_q == 'insured_party':
        payload['_internal']['insured_party'] = answer
        if "myself with child" in answer:
            payload['withChildren'] = True; payload['withSpouse'] = False
        elif "family" in answer:
            payload['withChildren'] = True; payload['withSpouse'] = True
        else: # Myself
            payload['withChildren'] = False; payload['withSpouse'] = False
    
    elif last_q == 'policyInceptionDate':
        try:
            date_str = answer.replace('/', '-')
            datetime.strptime(date_str, "%Y-%m-%d")
            payload['policyInceptionDate'] = date_str
        except ValueError:
            validation_error = "That doesn't look like a valid date format. Please use YYYY-MM-DD."

    elif last_q == 'email': payload['_internal']['email'] = user_message.strip()
    elif last_q == 'contact_mobile': payload['_internal']['contact_mobile'] = user_message.strip()
    
    # --- THIS LINE IS NOW FIXED ---
    elif last_q == 'promoCode':
        # If the answer is 'no', save an empty string, not None.
        payload['promoCode'] = "" if answer == 'no' else user_message.strip()
    # --- END OF FIX ---
    
    return payload, context, validation_error

def determine_next_question(payload: dict) -> str:
    """Determines the next question key to ask."""
    if payload.get('premiumType') is None: return 'premiumType'
    if payload.get('_internal', {}).get('insured_party') is None: return 'insured_party'
    if payload.get('policyInceptionDate') is None: return 'policyInceptionDate'
    if payload.get('_internal', {}).get('email') is None: return 'email'
    if payload.get('_internal', {}).get('contact_mobile') is None: return 'contact_mobile'
    if payload.get('promoCode') is None: return 'promoCode'
    return "DONE"

def finalize_payload(payload: dict) -> dict:
    """Removes temporary internal keys before finishing."""
    if '_internal' in payload:
        del payload['_internal']
    return payload