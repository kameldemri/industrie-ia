"""Tests for Module 3: Video Generation"""
import os
import ezdxf
from app.nodes.m3.node import generate_video


def test_generate_video_success():
    os.makedirs("outputs", exist_ok=True)
    dxf_path = "outputs/test_valve.dxf"
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()

    # Body
    msp.add_lwpolyline(
        [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)],
        close=True,
        dxfattribs={"layer": "BODY"}
    )
    # Bore
    msp.add_circle(
        center=(50, 50), radius=15,
        dxfattribs={"layer": "BORE"}
    )
    # Inlet
    msp.add_circle(
        center=(0, 50), radius=9,
        dxfattribs={"layer": "INLET"}
    )
    # Outlet
    msp.add_circle(
        center=(100, 50), radius=9,
        dxfattribs={"layer": "OUTLET"}
    )
    # Flanges
    msp.add_lwpolyline(
        [(40, 100), (60, 100), (60, 115), (40, 115), (40, 100)],
        close=True,
        dxfattribs={"layer": "FLANGE"}
    )
    msp.add_lwpolyline(
        [(40, 0), (60, 0), (60, -15), (40, -15), (40, 0)],
        close=True,
        dxfattribs={"layer": "FLANGE"}
    )
    doc.saveas(dxf_path)

    state = {
        "cad_paths": [dxf_path],
        "extracted_specs": {
            "part_name": "Valve DN100",
            "pressure": "40 bar",
            "material": "SS316L"
        }
    }
    result = generate_video(state)

    assert result["status_m3"] == "done"
    assert "video_path" in result
    assert result["video_path"] is not None


def test_generate_video_missing_input():
    state = {}
    result = generate_video(state)
    assert result["status_m3"] == "failed"
    assert "errors" in result


def test_generate_video_no_dxf_in_paths():
    state = {"cad_paths": ["outputs/something.ifc"]}
    result = generate_video(state)
    assert result["status_m3"] == "failed"
    assert "errors" in result