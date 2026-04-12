"""Tests for Module 2"""
from app.nodes.m2.node import generate_cad

def test_generate_cad_returns_delta():
    state = {"status_m2": None, "errors": []}
    result = generate_cad(state)
    assert isinstance(result, dict)
