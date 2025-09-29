import re
from enum import Enum
import logging
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from utils.llm_services import llm
logger = logging.getLogger(__name__)

class Product(str, Enum):
    TRAVEL = "TRAVEL"
    FAMILY = "FAMILY"
    POLICY_CLAIM_STATUS = "POLICY_CLAIM_STATUS"
    UNKNOWN = "UNKNOWN"

class Intent(BaseModel):
    product: Product = Field(default=Product.UNKNOWN)
    intent: str
    confidence: float = Field(default=0.8)
    requires_clarification: bool = Field(default=False)

chain = llm.with_structured_output(Intent, method="function_calling")

def get_primary_intent(user_message: str, chat_history: list) -> Intent:
    try:
        prompt = [
            SystemMessage(
                content="""You are an expert AI assistant for HLAS. Your role is to classify user messages to determine the product and intent.

                Available products are:
                - 'TRAVEL': For travel insurance, trip insurance, Travel Protect360.
                - 'FAMILY': For family insurance, Family Protect360.

                CRITICAL RULES:
                - If you see words like "travel", "trip", "Travel Protect360" -> set product to TRAVEL.
                - If you see words like "family", "family protect" -> set product to FAMILY.
                """
            ),
            HumanMessage(content=f"Chat History:\n{chat_history}\n\nUser Message: {user_message}"),
        ]
        result = chain.invoke(prompt)
        logger.info(f"PRIMARY INTENT AGENT RESULT: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in intent classification: {str(e)}")
        return Intent(product=Product.UNKNOWN, intent="unwanted")