"""Tests for Module 4"""
from app.nodes.m4.node import source_suppliers

def test_source_suppliers_returns_delta():
    state = {"status_m4": None, "errors": []}
    result = source_suppliers(state)
    assert isinstance(result, dict)
