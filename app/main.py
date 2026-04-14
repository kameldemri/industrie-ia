from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.graph import pipeline

app = FastAPI(title="INDUSTRIE IA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TriggerRequest(BaseModel):
    input_file: str
    input_prompt: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/trigger")
def trigger(request: TriggerRequest):

    state = {
        "input_file": request.input_file,
        "input_prompt": request.input_prompt
    }

    # 🔥 IMPORTANT FIX HERE
    result = pipeline.invoke(
        state,
        config={
            "configurable": {
                "thread_id": "demo_thread"
            }
        }
    )

    return {
        "status": "success",
        "result": result
    }