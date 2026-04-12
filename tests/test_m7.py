"""Tests for Module 7"""
from app.nodes.m7.node import generate_business_plan

def test_generate_business_plan_returns_delta():
    state = {"status_m7": None, "errors": []}
    result = generate_business_plan(state)
    assert isinstance(result, dict)
