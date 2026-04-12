"""Tests for Module 5"""
from app.nodes.m5.node import simulate_negotiation

def test_simulate_negotiation_returns_delta():
    state = {"status_m5": None, "errors": []}
    result = simulate_negotiation(state)
    assert isinstance(result, dict)
