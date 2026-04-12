import os
from langchain_openai import ChatOpenAI

def get_llm():
    """
    Returns a configured LangChain ChatOpenAI instance.
    Automatically routes to local Ollama or external APIs based on .env.
    """
    base_url = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")
    api_key = os.getenv("LLM_API_KEY", "unused")
    model = os.getenv("LLM_MODEL_NAME", "mistral")

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
        max_retries=2,
    )
