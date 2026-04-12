"""Tests for Module 9"""
from app.nodes.m9.node import export_catalog

def test_export_catalog_returns_delta():
    state = {"status_m9": None, "errors": []}
    result = export_catalog(state)
    assert isinstance(result, dict)
