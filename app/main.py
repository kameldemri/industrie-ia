from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.graph import pipeline

app = FastAPI(title="INDUSTRIE IA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "industrie-ia", "db": "sqlite_connected"}

@app.post("/api/v1/trigger")
async def trigger_pipeline():
    return {"status": "pipeline_triggered", "thread_id": "demo_run"}
