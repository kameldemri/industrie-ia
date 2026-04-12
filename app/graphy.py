from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import PipelineState

def build_graph():
    graph = StateGraph(PipelineState)
    # Temporary edge to allow compilation before nodes are added
    graph.add_edge(START, END)
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

# Export this exact name for main.py to import
pipeline = build_graph()
