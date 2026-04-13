import json
from langchain_community.llms import Ollama
# =========================
# CONFIG LLM
# =========================
MODEL_NAME = "mistral"
llm = Ollama(model=MODEL_NAME)

# =========================
# 1. CALL LLM RAW
# =========================
def call_llm(prompt: str) -> str:
    try:
        return llm.invoke(prompt)
    except Exception as e:
        return f"ERROR: {str(e)}"


# =========================
# 2. SAFE JSON PARSER
# =========================
def extract_json(response: str) -> dict:
    try:
        start = response.find("{")
        end = response.rfind("}") + 1

        # FIX: was checking end == -1, but rfind()+1 returns 0 when not found
        if start == -1 or end == 0:
            return {}

        return json.loads(response[start:end])

    except Exception:
        return {}


# =========================
# 3. MAIN FUNCTION (USED BY ALL MODULES)
# =========================
def llm_extract(prompt: str, mode: str = "json"):
    response = call_llm(prompt)

    if mode == "json":
        return extract_json(response)

    return response