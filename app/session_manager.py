import os
import redis
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# --- Redis Connection ---
try:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    SESSION_EXPIRE_SECONDS = 86400 # 24 hours
    
    # Create a reusable connection pool
    redis_pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    logger.info(f"Redis connection pool created for {REDIS_HOST}:{REDIS_PORT}")

except Exception as e:
    logger.critical(f"Failed to create Redis connection pool: {e}")
    redis_pool = None

def get_redis_connection():
    """Get a connection from the pool."""
    if not redis_pool:
        raise ConnectionError("Redis pool is not initialized.")
    return redis.Redis(connection_pool=redis_pool)

def get_default_session(session_id: str) -> Dict[str, Any]:
    """Returns the structure for a new session."""
    return {
        "session_id": session_id,
        "stage": "initial",
        "chat_history": [],
        "collected_info": {},
        "conversation_context": {
            "primary_product": "UNKNOWN",
            "last_intent": None,
            "error_count": 0,
        },
        "last_active": datetime.now().isoformat()
    }

def get_session(session_id: str) -> Dict[str, Any]:
    """
    Retrieves the full session object from Redis.
    If no session exists, creates a new one with an expiry.
    """
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        session_data = r.get(session_key)
        
        if not session_data:
            logger.info(f"No session found for {session_id}. Creating new session.")
            new_session = get_default_session(session_id)
            # Store with expiry
            r.set(session_key, json.dumps(new_session), ex=SESSION_EXPIRE_SECONDS)
            return new_session
        
        # Session exists, return and reset expiry
        r.expire(session_key, SESSION_EXPIRE_SECONDS)
        return json.loads(session_data)
            
    except Exception as e:
        logger.error(f"Error in get_session for {session_id}: {str(e)}")
        # Return a default session structure on error
        return get_default_session(session_id)

def update_session(session_id: str, user_message: str, agent_response: str):
    """
    Updates the chat history and last_active timestamp, and resets expiry.
    """
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        # Use a transaction to safely update the session
        with r.pipeline() as pipe:
            while True:
                try:
                    # Watch the key for changes
                    pipe.watch(session_key)
                    
                    # Get current session
                    session_data_str = pipe.get(session_key)
                    if session_data_str:
                        session = json.loads(session_data_str)
                    else:
                        session = get_default_session(session_id)
                    
                    # Modify data
                    session["chat_history"].append(("user", user_message))
                    session["chat_history"].append(("assistant", agent_response))
                    
                    # Keep history to a reasonable limit (e.g., last 50 exchanges)
                    session["chat_history"] = session["chat_history"][-100:]
                    
                    session["last_active"] = datetime.now().isoformat()
                    
                    # Start transaction
                    pipe.multi()
                    pipe.set(session_key, json.dumps(session))
                    pipe.expire(session_key, SESSION_EXPIRE_SECONDS) # Reset expiry
                    pipe.execute()
                    break # Success
                    
                except redis.WatchError:
                    # Session was modified by another process, retry
                    logger.warning(f"WatchError for {session_key}, retrying update_session.")
                    continue
                    
    except Exception as e:
        logger.error(f"Error in update_session for {session_id}: {str(e)}")

def get_chat_history(session_id: str) -> List:
    """Gets only the chat_history from the session."""
    session = get_session(session_id)
    return session.get("chat_history", [])

def get_stage(session_id: str) -> str:
    """Gets the current stage from the session."""
    session = get_session(session_id)
    return session.get("stage", "initial")

def _update_session_field(session_id: str, field: str, value: Any):
    """Helper function to update a single top-level field and reset expiry."""
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(session_key)
                    session_data_str = pipe.get(session_key)
                    session = json.loads(session_data_str) if session_data_str else get_default_session(session_id)
                    
                    session[field] = value
                    session["last_active"] = datetime.now().isoformat()
                    
                    pipe.multi()
                    pipe.set(session_key, json.dumps(session))
                    pipe.expire(session_key, SESSION_EXPIRE_SECONDS) # Reset expiry
                    pipe.execute()
                    break
                except redis.WatchError:
                    logger.warning(f"WatchError for {session_key}, retrying _update_session_field.")
                    continue
    except Exception as e:
        logger.error(f"Error in _update_session_field for {session_id} (field: {field}): {str(e)}")

def set_stage(session_id: str, stage: str):
    """Sets the current stage for the session."""
    _update_session_field(session_id, "stage", stage)

def get_collected_info(session_id: str) -> Dict[str, Any]:
    """Gets the collected_info from the session."""
    session = get_session(session_id)
    return session.get("collected_info", {})

def set_collected_info(session_id: str, key: str, value: Any):
    """Updates a specific key within the collected_info object."""
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(session_key)
                    session_data_str = pipe.get(session_key)
                    session = json.loads(session_data_str) if session_data_str else get_default_session(session_id)
                    
                    if "collected_info" not in session:
                        session["collected_info"] = {}
                    session["collected_info"][key] = value
                    session["last_active"] = datetime.now().isoformat()
                    
                    pipe.multi()
                    pipe.set(session_key, json.dumps(session))
                    pipe.expire(session_key, SESSION_EXPIRE_SECONDS) # Reset expiry
                    pipe.execute()
                    break
                except redis.WatchError:
                    logger.warning(f"WatchError for {session_key}, retrying set_collected_info.")
                    continue
    except Exception as e:
        logger.error(f"Error in set_collected_info for {session_id} (key: {key}): {str(e)}")

def update_conversation_context(session_id: str, **kwargs):
    """Updates keys within the conversation_context object."""
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(session_key)
                    session_data_str = pipe.get(session_key)
                    session = json.loads(session_data_str) if session_data_str else get_default_session(session_id)
                    
                    if "conversation_context" not in session:
                        session["conversation_context"] = {}
                    
                    for key, value in kwargs.items():
                        session["conversation_context"][key] = value
                    session["last_active"] = datetime.now().isoformat()
                    
                    pipe.multi()
                    pipe.set(session_key, json.dumps(session))
                    pipe.expire(session_key, SESSION_EXPIRE_SECONDS) # Reset expiry
                    pipe.execute()
                    break
                except redis.WatchError:
                    logger.warning(f"WatchError for {session_key}, retrying update_conversation_context.")
                    continue
    except Exception as e:
        logger.error(f"Error in update_conversation_context for {session_id}: {str(e)}")

def increment_error_count(session_id: str):
    """Increments the error_count in the conversation_context."""
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        
        with r.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(session_key)
                    session_data_str = pipe.get(session_key)
                    session = json.loads(session_data_str) if session_data_str else get_default_session(session_id)
                    
                    if "conversation_context" not in session:
                        session["conversation_context"] = {}
                    
                    current_count = session["conversation_context"].get("error_count", 0)
                    session["conversation_context"]["error_count"] = current_count + 1
                    session["last_active"] = datetime.now().isoformat()
                    
                    pipe.multi()
                    pipe.set(session_key, json.dumps(session))
                    pipe.expire(session_key, SESSION_EXPIRE_SECONDS) # Reset expiry
                    pipe.execute()
                    break
                except redis.WatchError:
                    logger.warning(f"WatchError for {session_key}, retrying increment_error_count.")
                    continue
    except Exception as e:
        logger.error(f"Error in increment_error_count for {session_id}: {str(e)}")

def clear_session_for_global_reset(session_id: str):
    """
    Wipes the session and resets it to the default initial state.
    Used for "hi"/"hello" global reset.
    """
    try:
        r = get_redis_connection()
        session_key = f"session:{session_id}"
        new_session = get_default_session(session_id)
        r.set(session_key, json.dumps(new_session), ex=SESSION_EXPIRE_SECONDS)
        logger.info(f"Global reset for session {session_id} completed.")
    except Exception as e:
        logger.error(f"Error in clear_session_for_global_reset for {session_id}: {str(e)}")

def clear_collected_info(session_id: str):
    """
    Clears only the 'collected_info' field.
    Used for product/context switches.
    """
    _update_session_field(session_id, "collected_info", {})
    logger.info(f"Cleared collected_info for session {session_id}.")