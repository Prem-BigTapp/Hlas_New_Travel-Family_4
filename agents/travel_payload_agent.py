import logging
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.session_manager import get_session, set_collected_info, set_stage, update_conversation_context

logger = logging.getLogger(__name__)

def get_country_code_map() -> dict:
    """
    A simple, editable dictionary to map user-input destinations to your specific API codes.
    You can easily add new countries here.
    """
    return {
        'albania': 'ALB', 'antarctica': 'ATA', 'argentina': 'ARG',
        'australia': 'AUS', 'austria': 'AUS', 'bahrain': 'BAH',
        'bangladesh': 'BAN', 'belgium': 'BEL', 'bhutan': 'BTU',
        'bolivia': 'BOL', 'bosnia and herzegovina': 'BIH', 'brazil': 'BRA',
        'brunei': 'BRU', 'bulgaria': 'BUL', 'cambodia': 'CAM',
        'canada': 'CAN', 'cayman islands': 'CYM', 'chile': 'CHL',
        'china (excluding inner mongolia)': 'CHI', 'colombia': 'COL',
        'costa rica': 'COS', 'croatia': 'HRV', 'cruise to nowhere': 'CRU',
        'cyprus': 'CYP', 'czech republic': 'CZE', 'denmark': 'DEN',
        'egypt': 'EGY', 'estonia': 'EST', 'fiji': 'FJI',
        'finland': 'FIN', 'france': 'FRA', 'french polynesia': 'PYF',
        'germany': 'GER', 'greece': 'GRE', 'hong kong': 'HKG',
        'hungary': 'HUN', 'iceland': 'ICE', 'india': 'INN',
        'indonesia': 'IND', 'ireland': 'IRE', 'israel': 'ISR',
        'italy': 'ITA', 'japan': 'JPN', 'jordan': 'JOR',
        'kazakhstan': 'KAZ', 'kenya': 'KEN', 'korea': 'KOR',
        'kuwait': 'KUW', 'kyrgyzstan': 'KGZ', 'laos': 'LAO'
    }


# --- Payload Templates ---
def get_single_trip_template() -> dict:
    """Returns the base payload for Single Trip policies (TVP)."""
    return {
        "ProductCode": "TVP", "media": {"wcc": "HLS"},
        "travel": {
            "policy_type": "single", "country_code": [], "number_of_days": None,
            "zone": None, "with_children": "no", "with_spouse": "no",
            "with_group_of_adults": "no", "with_group_of_households": "no",
            "plan": "gold",
            "selectedAddOns": {},
            "number_of_travellers": { "total": None, "child": [], "adult": [], "group": 1 }
        },
        "promotion": {"coupon_code": ""}, "leads": {"email": None, "contact_mobile": None}, "CEPParams": {}
    }

def get_annual_trip_template() -> dict:
    """Returns the base payload for Annual Multi-Trip policies (TPX)."""
    return {
        "ProductCode": "TPX", "media": {"wcc": "HLS"},
        "travel": {
            "policy_type": "annual", "country_code": None, "number_of_days": 1,
            "zone": None, "with_children": "no", "with_spouse": "no",
            "with_group_of_adults": "no", "with_group_of_households": "no",
            "plan": "gold",
            "selectedAddOns": {},
            "number_of_travellers": { "total": None, "child": [], "adult": [], "group": 1 }
        },
        "promotion": {"coupon_code": ""}, "leads": {"email": None, "contact_mobile": None}, "CEPParams": {}
    }

# --- Question Definitions ---
QUESTION_MAP = {
    'policy_type': "Are you looking for a **Single Trip** or an **Annual Multi-Trip** policy?",
    'group_type_single': "Who will be traveling? (Yourself, Family, Group of Adults, or Group of Family)",
    'group_type_annual': "Who will this annual plan cover? (Yourself or Family)",
    'zone': "Which region do you need coverage for? (**Asia** or **Worldwide**)",
    'num_adults': "How many adults?",
    'num_children': "How many children?",
    'num_adults_group': "How many adults are in the group?",
    'num_households': "How many families (households) are traveling together?",
    'household_info': "For family #{num}, how many adults and children?",
    'destination': "Where are you traveling to? You can enter one or more countries separated by commas (max 10).",
    'start_date': "What is your travel start date (YYYY-MM-DD)?",
    'end_date': "And what is your travel end date (YYYY-MM-DD)?",
    'addon_pre_ex': "Do you need coverage for pre-existing medical conditions? (yes/no)",
    'addon_ffm': "Add coverage for Loss of Frequent Flyer Miles? (yes/no)",
    'addon_flight_delay': "Add the Flight Delay benefit? (yes/no)",
    'coupon_code': "Do you have a coupon code? (If not, just say 'no')",
    'email': "What is your email address?",
    'contact_mobile': "Finally, what is your 8-digit contact mobile number?",
}

# --- Main Agent Logic ---
def run_travel_payload_agent(user_message: str, chat_history: list, session_id: str) -> dict:
    session = get_session(session_id)
    context = session.get("conversation_context", {})
    payload = session.get("collected_info", {}).get("payload")
    
    if not context.get('current_question_key'):
        update_conversation_context(session_id, current_question_key='policy_type')
        return {"output": QUESTION_MAP['policy_type']}

    payload, context, validation_error = process_user_answer(user_message, payload, context, session_id)
    if validation_error:
        return {"output": validation_error}

    next_question_key = determine_next_question(payload, context)
    
    if next_question_key == "DONE":
        payload = finalize_payload(payload, context)
        logger.info("--- FINAL POPULATED PAYLOAD ---")
        logger.info(json.dumps(payload, indent=4))
        logger.info("--- END OF PAYLOAD ---")
        
        set_collected_info(session_id, "payload", payload)
        set_stage(session_id, "quote_generation")
        update_conversation_context(session_id, current_question_key=None)
        return {"output": "Thank you, I have all the information. Generating your quote now..."}
    else:
        question_text = QUESTION_MAP[next_question_key]
        if '#num' in question_text:
            question_text = question_text.replace('#num', str(context.get('households_collected', 0) + 1))
        
        update_conversation_context(session_id, current_question_key=next_question_key)
        set_collected_info(session_id, "payload", payload)
        return {"output": question_text}

def process_user_answer(user_message: str, payload: dict, context: dict, session_id: str) -> Tuple[dict, dict, Optional[str]]:
    last_q = context.get('current_question_key')
    answer = user_message.strip()
    validation_error = None

    if last_q == 'policy_type':
        if 'annual' in answer.lower(): context['policy_type_choice'] = 'annual'; payload = get_annual_trip_template()
        else: context['policy_type_choice'] = 'single'; payload = get_single_trip_template()
    
    elif last_q == 'group_type_single':
        ans_lower = answer.lower()
        if 'group of families' in ans_lower or 'households' in ans_lower: context['group_type_choice'] = 'group_family'
        elif 'group of adults' in ans_lower: context['group_type_choice'] = 'group_adults'
        elif 'family' in ans_lower: context['group_type_choice'] = 'family'
        else: context['group_type_choice'] = 'myself'
    elif last_q == 'group_type_annual':
        if 'family' in answer.lower(): context['group_type_choice'] = 'family'
        else: context['group_type_choice'] = 'myself'

    elif last_q == 'zone':
        if 'asia' in answer.lower(): payload['travel']['zone'] = 'A2'
        else: payload['travel']['zone'] = 'A3'

    # --- NEW LOGIC START: Multi-country processing and validation ---
    elif last_q == 'destination':
        country_map = get_country_code_map()
        entered_countries = [c.strip().lower() for c in answer.split(',')]
        
        if len(entered_countries) > 10:
            return payload, context, "You can select a maximum of 10 countries. Please provide your destination(s) again."

        country_codes = []
        unknown_countries = []
        for country_name in entered_countries:
            code = country_map.get(country_name)
            if code:
                country_codes.append(code)
            else:
                unknown_countries.append(country_name)
        
        if unknown_countries:
            return payload, context, f"I don't have information for: {', '.join(unknown_countries)}. Please choose from the available destinations."
        
        payload['travel']['country_code'] = country_codes
    # --- NEW LOGIC END ---
    
    elif last_q == 'start_date': context['start_date'] = answer.replace('/', '-')
    elif last_q == 'end_date': context['end_date'] = answer.replace('/', '-')
    
    elif last_q == 'num_adults': context['num_adults'] = int(answer)
    
    # --- NEW LOGIC START: Annual-Family validation ---
    elif last_q == 'num_children':
        context['num_children'] = int(answer)
        adults = context.get('num_adults', 0)
        children = context.get('num_children', 0)
        if context.get('policy_type_choice') == 'annual' and context.get('group_type_choice') == 'family' and (adults > 2 or children > 5):
            validation_error = "For an Annual Family plan, the maximum is 2 adults and 5 children. Let's start over with the number of travelers."
            context.pop('num_adults', None)
            context.pop('num_children', None)
            context['current_question_key'] = 'num_adults'
    # --- NEW LOGIC END ---
    
    elif last_q == 'num_adults_group': context['num_adults_group'] = int(answer)
    elif last_q == 'num_households':
        context['num_households'] = int(answer); context['households_to_collect'] = int(answer)
        context['households_collected'] = 0; context['households_data'] = []
    elif last_q == 'household_info':
        parts = [p.strip() for p in answer.replace('and', ',').split(',')]; adults = int(parts[0]); children = int(parts[1])
        context['households_data'].append({'adults': adults, 'children': children})
        context['households_collected'] = context.get('households_collected', 0) + 1
    elif last_q.startswith('addon_'):
        is_selected = 'yes' in answer.lower()
        if last_q == 'addon_pre_ex': payload['travel']['selectedAddOns']['preExAddOn'] = {'selected': is_selected}
        elif last_q == 'addon_ffm': payload['travel']['selectedAddOns']['lossFFMAddOn'] = {'selected': is_selected}
        elif last_q == 'addon_flight_delay': payload['travel']['selectedAddOns']['flightDelayAddOn'] = {'selected': is_selected}
    elif last_q == 'coupon_code': payload['promotion']['coupon_code'] = "" if 'no' in answer.lower() else answer
    elif last_q == 'email': payload['leads']['email'] = answer
    elif last_q == 'contact_mobile': payload['leads']['contact_mobile'] = answer

    update_conversation_context(session_id, **context)
    return payload, context, validation_error

def determine_next_question(payload: dict, context: dict) -> str:
    policy_type = context.get('policy_type_choice')
    group_type = context.get('group_type_choice')
    if not group_type: return 'group_type_annual' if policy_type == 'annual' else 'group_type_single'
    if policy_type == 'annual':
        if not payload.get('travel', {}).get('zone'): return 'zone'
        if group_type == 'family' and context.get('num_adults') is None: return 'num_adults'
        if group_type == 'family' and context.get('num_children') is None: return 'num_children'
        if not payload.get('travel', {}).get('selectedAddOns', {}).get('preExAddOn'): return 'addon_pre_ex'
    else:
        if group_type == 'family' and context.get('num_adults') is None: return 'num_adults'
        if group_type == 'family' and context.get('num_children') is None: return 'num_children'
        if group_type == 'group_adults' and context.get('num_adults_group') is None: return 'num_adults_group'
        if group_type == 'group_family' and context.get('num_households') is None: return 'num_households'
        if group_type == 'group_family' and context.get('households_collected', 0) < context.get('households_to_collect', 0): return 'household_info'
        if not payload.get('travel', {}).get('country_code'): return 'destination'
        if not context.get('start_date'): return 'start_date'
        if not context.get('end_date'): return 'end_date'
        addons = payload.get('travel', {}).get('selectedAddOns', {})
        if 'preExAddOn' not in addons: return 'addon_pre_ex'
        if 'lossFFMAddOn' not in addons: return 'addon_ffm'
        if 'flightDelayAddOn' not in addons: return 'addon_flight_delay'
    if payload.get('promotion', {}).get('coupon_code') is None: return 'coupon_code'
    if not payload.get('leads', {}).get('email'): return 'email'
    if not payload.get('leads', {}).get('contact_mobile'): return 'contact_mobile'
    return "DONE"

def finalize_payload(payload: dict, context: dict) -> dict:
    group_type = context.get('group_type_choice')
    if group_type == 'myself': payload['travel']['number_of_travellers'].update({'adult': [1], 'child': [0], 'total': 1})
    elif group_type == 'family':
        adults = context.get('num_adults', 0); children = context.get('num_children', 0)
        payload['travel']['number_of_travellers'].update({'adult': [adults], 'child': [children], 'total': adults + children})
        if children > 0: payload['travel']['with_children'] = 'yes'
        if adults > 1: payload['travel']['with_spouse'] = 'yes'
    elif group_type == 'group_adults':
        adults = context.get('num_adults_group', 0)
        payload['travel']['number_of_travellers'].update({'adult': [1] * adults, 'child': [0] * adults, 'total': adults})
        payload['travel']['with_group_of_adults'] = 'yes'
    elif group_type == 'group_family':
        households_data = context.get('households_data', [])
        adults_list = [h['adults'] for h in households_data]; children_list = [h['children'] for h in households_data]
        total = sum(adults_list) + sum(children_list)
        payload['travel']['number_of_travellers'].update({'adult': adults_list, 'child': children_list, 'total': total, 'group': len(households_data)})
        payload['travel']['with_group_of_households'] = 'yes'
        payload['travel']['households_info'] = [{'with_children': 'yes' if h['children'] > 0 else 'no', 'with_spouse': 'yes' if h['adults'] > 1 else 'no'} for h in households_data]
    if context.get('policy_type_choice') == 'single':
        start = datetime.strptime(context['start_date'], "%Y-%m-%d").date(); end = datetime.strptime(context['end_date'], "%Y-%m-%d").date()
        payload['travel']['number_of_days'] = max((end - start).days + 1, 1)
    return payload