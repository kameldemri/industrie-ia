"""Tests for Module 6"""
from app.nodes.m6.node import calculate_tco

def test_calculate_tco_returns_delta():
    state = {"status_m6": None, "errors": []}
    result = calculate_tco(state)
    assert isinstance(result, dict)
