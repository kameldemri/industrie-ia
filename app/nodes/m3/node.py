"""Module 3: Produce HD project presentation video (DXF → Manim)"""

import os
import json
import uuid
import subprocess
from typing import Dict, Any, List

import ezdxf
from app.state import PipelineState


# =========================
# DXF → OBJECTS PARSER
# =========================

def parse_dxf_to_objects(dxf_path: str) -> List[Dict[str, Any]]:
    """Convert DXF entities into simplified 3D objects for Manim."""

    objects = []

    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        for e in msp:

            if e.dxftype() == "CIRCLE":
                raw_radius = float(e.dxf.radius)
                normalized_radius = max(0.3, min(raw_radius / 10, 3.0))
                objects.append({
                    "type": "cylinder",
                    "radius": normalized_radius,
                    "height": normalized_radius * 1.5,
                    "layer": e.dxf.layer
                })

            elif e.dxftype() == "LWPOLYLINE":
                pts = list(e.get_points())
                if len(pts) >= 4:
                    x_vals = [p[0] for p in pts]
                    y_vals = [p[1] for p in pts]
                    width = max(x_vals) - min(x_vals)
                    height = max(y_vals) - min(y_vals)
                    normalized_width = max(0.5, min(width / 20, 5.0))
                    normalized_height = max(0.3, min(height / 20, 3.0))
                    objects.append({
                        "type": "box",
                        "width": normalized_width,
                        "height": normalized_height,
                        "layer": e.dxf.layer
                    })

    except Exception as e:
        print("DXF parse error:", e)

    return objects


# =========================
# MAIN MODULE 3 NODE
# =========================

def generate_video(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 3 (DXF-driven Manim renderer)."""

    try:
        cad_paths = state.get("cad_paths", [])

        if not cad_paths:
            return {
                **state,
                "status_m3": "failed",
                "errors": state.get("errors", []) + ["M3: missing cad_paths from M2"]
            }

        dxf_file = next((p for p in cad_paths if p.endswith(".dxf")), None)

        if not dxf_file:
            return {
                **state,
                "status_m3": "failed",
                "errors": state.get("errors", []) + ["M3: no DXF file found in cad_paths"]
            }

        objects = parse_dxf_to_objects(dxf_file)

        if not objects:
            objects = [{"type": "box", "width": 2, "height": 1, "layer": "DEFAULT"}]

        os.makedirs("outputs", exist_ok=True)

        file_id = str(uuid.uuid4())
        script_path = f"outputs/m3_{file_id}.py"

        # Pull real specs from M1
        extracted = state.get("extracted_specs", {})
        part_name = str(extracted.get("part_name", "DXF Model")).replace('"', '\\"')
        specs_pressure = str(extracted.get("pressure", "N/A")).replace('"', '\\"')
        specs_material = str(extracted.get("material", "Steel")).replace('"', '\\"')

        objects_json = json.dumps(objects)

        # =========================
        # WRITE MANIM SCRIPT
        # =========================
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"""\
from manim import *
import json

OBJECTS = {objects_json}

LAYER_COLORS = {{
    "BODY":    "#8090A0",
    "BORE":    "#2196F3",
    "INLET":   "#4CAF50",
    "OUTLET":  "#F44336",
    "FLANGE":  "#FF9800",
    "DEFAULT": "#8090A0"
}}

class GeneratedScene(ThreeDScene):

    def construct(self):
        self.set_camera_orientation(phi=60*DEGREES, theta=45*DEGREES)
        self.camera.set_zoom(0.8)

        title = Text("{part_name}", font_size=28).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title)
        self.play(Write(title))

        # Find body dimensions for positioning other shapes
        body = next((o for o in OBJECTS if o.get("layer") == "BODY"), None)
        body_w = body["width"] if body else 2
        body_h = body["height"] if body else 1

        shapes = []
        flange_count = 0

        for obj in OBJECTS:
            layer = obj.get("layer", "DEFAULT")
            color = LAYER_COLORS.get(layer, "#8090A0")

            if obj["type"] == "cylinder":
                shape = Cylinder(radius=obj["radius"], height=obj["height"])
                shape.set_color(color)

                if layer == "BORE":
                    # Bore sits at center of body
                    shape.move_to(ORIGIN)

                elif layer == "INLET":
                    # Inlet pipe comes from the left
                    shape.rotate(PI/2, axis=UP)
                    shape.move_to(LEFT * (body_w / 2))

                elif layer == "OUTLET":
                    # Outlet pipe goes to the right
                    shape.rotate(PI/2, axis=UP)
                    shape.move_to(RIGHT * (body_w / 2))

                else:
                    shape.move_to(ORIGIN)

                shapes.append(shape)

            elif obj["type"] == "box":
                shape = Cube()
                shape.stretch(obj["width"], 0)
                shape.stretch(obj["height"], 1)
                shape.set_color(color)

                if layer == "BODY":
                    # Body is the main container, semi-transparent
                    shape.set_opacity(0.3)
                    shape.move_to(ORIGIN)

                elif layer == "FLANGE":
                    # First flange on top, second on bottom
                    shape.set_opacity(0.7)
                    if flange_count == 0:
                        shape.move_to(UP * (body_h / 2 + 0.3))
                    else:
                        shape.move_to(DOWN * (body_h / 2 + 0.3))
                    flange_count += 1

                else:
                    shape.set_opacity(0.5)
                    shape.move_to(ORIGIN)

                shapes.append(shape)

        self.play(Create(VGroup(*shapes)), run_time=2)
        self.begin_ambient_camera_rotation(rate=0.2)
        self.wait(4)

        specs = Text("{specs_pressure} | {specs_material}", font_size=24).to_edge(DOWN)
        self.add_fixed_in_frame_mobjects(specs)
        self.play(Write(specs))
        self.wait(2)
""")

        # =========================
        # RENDER VIDEO
        # =========================
        cmd = [
            "python", "-m", "manim",
            "-ql",
            "--media_dir", "outputs",
            script_path,
            "GeneratedScene"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {
                **state,
                "status_m3": "failed",
                "errors": state.get("errors", []) + [result.stderr]
            }

        scene_dir = f"outputs/videos/m3_{file_id}/480p15"
        mp4_path = f"{scene_dir}/GeneratedScene.mp4"
        avi_path = f"{scene_dir}/GeneratedScene.avi"

        # =========================
        # CONVERT TO AVI
        # =========================
        try:
            import ffmpeg
            ffmpeg.input(mp4_path).output(avi_path).run(overwrite_output=True, quiet=True)
        except Exception:
            avi_path = None

        return {
            **state,
            "m3_script": script_path,
            "video_path": mp4_path,
            "video_path_avi": avi_path,
            "status_m3": "done"
        }

    except Exception as e:
        return {
            **state,
            "status_m3": "failed",
            "errors": state.get("errors", []) + [f"M3: {str(e)}"]
        }