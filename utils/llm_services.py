import os
import logging
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from dotenv import load_dotenv

# Load the environment variables from your .env file
load_dotenv()

logger = logging.getLogger(__name__)

llm = None
embedding_model = None

try:
    # Check if the required environment variables are set
    if not all([
        os.getenv("AZURE_OPENAI_API_KEY"),
        os.getenv("AZURE_OPENAI_ENDPOINT"),
        os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
    ]):
        raise ValueError("One or more required Azure OpenAI environment variables are not set.")

    # Initialize the Azure Chat LLM
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        temperature=0, # Set to 0 for deterministic, rule-based responses
        max_retries=2,
    )
    logger.info("Successfully initialized Azure OpenAI LLM.")

    # Initialize the Azure Embedding Model for RAG capabilities
    embedding_model = AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
    )
    logger.info("Successfully initialized Azure OpenAI Embedding model.")

except Exception as e:
    logger.error(f"Failed to initialize Azure OpenAI services: {e}")
    llm = None
    embedding_model = None