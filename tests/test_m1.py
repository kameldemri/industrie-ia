"""Tests for Module 1"""
from app.nodes.m1.node import extract_specs

def test_extract_specs_returns_delta():
    state = {"status_m1": None, "errors": []}
    result = extract_specs(state)
    assert isinstance(result, dict)
