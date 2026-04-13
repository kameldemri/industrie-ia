from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import PipelineState

# adding m6 and m7
from app.nodes.m6.node import calculate_tco
from app.nodes.m7.node import generate_business_plan
 
def build_graph():
    graph = StateGraph(PipelineState)
    
    
    graph.add_node("m6", calculate_tco)
    graph.add_node("m7", generate_business_plan)
    graph.add_edge("m6", "m7")
    
    
    # Edge removed: causes KeyError: '__end__' on empty graphs in LangGraph 0.2.x
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

pipeline = build_graph()
