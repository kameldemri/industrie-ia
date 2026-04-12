"""Tests for Module 8"""
from app.nodes.m8.node import simulate_digital_twin

def test_simulate_digital_twin_returns_delta():
    state = {"status_m8": None, "errors": []}
    result = simulate_digital_twin(state)
    assert isinstance(result, dict)
