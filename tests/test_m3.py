"""Tests for Module 3"""
from app.nodes.m3.node import generate_video

def test_generate_video_returns_delta():
    state = {"status_m3": None, "errors": []}
    result = generate_video(state)
    assert isinstance(result, dict)
