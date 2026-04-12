from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import PipelineState

def build_graph():
    graph = StateGraph(PipelineState)
    # Edge removed: causes KeyError: '__end__' on empty graphs in LangGraph 0.2.x
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

pipeline = build_graph()
