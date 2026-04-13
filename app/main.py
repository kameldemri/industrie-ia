from fastapi import FastAPI
from pydantic import BaseModel
from app.graph import build_graph

app = FastAPI()
graph = build_graph()

# =========================
# INPUT MODEL
# =========================
class InputData(BaseModel):
    input_file: str | None = None
    input_prompt: str | None = None

# =========================
# ENDPOINT SAFE
# =========================
@app.post("/trigger")
def trigger(data: InputData):

    # init state
    state = {
        "input_file": data.input_file,
        "input_prompt": data.input_prompt
    }

    try:
        # RUN GRAPH
        result = graph.invoke(state)

        if not isinstance(result, dict):
            return {
                "status": "error",
                "message": "Invalid graph output"
            }

        return {
            "M1_result": result.get("M1_result", {}),
            "M4_result": result.get("M4_result", []),

            "files": {
                "M1": (
                    result.get("M1_result", {}) or {}
                ).get("output_file"),

                "M4": result.get("M4_output_file")
            },

            "status": "success"
        }

    except Exception as e:
        # 🔥 IMPORTANT: NEVER RETURN 500 RAW
        print("❌ API ERROR:", str(e))

        return {
            "status": "error",
            "message": str(e),
            "M1_result": {},
            "M4_result": [],
            "files": {}
        }
