"""Module 2: Generate 2D/3D CAD plans (DXF, IFC) from extracted specs"""
import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from app.state import PipelineState
import ezdxf
import ifcopenshell
import ifcopenshell.guid

class CADSpecs(BaseModel):
    model_config = ConfigDict(extra="allow")
    part_name: str = "INDUSTRIE_IA_Part"
    length_mm: float = Field(100.0, ge=0.01)
    width_mm: float = Field(100.0, ge=0.01)
    height_mm: float = Field(50.0, ge=0.01)
    material: str = "Steel"
    pressure: str = "N/A"

def generate_cad(state: PipelineState) -> Dict[str, Any]:
    """LangGraph node for Module 2."""
    errors = list(state.get("errors", []))
    cad_paths: List[str] = []

    try:
        raw = state.get("extracted_specs", {})
        if not raw or not isinstance(raw, dict):
            errors.append("M2: extracted_specs missing. Using defaults.")
            raw = {}
        try:
            specs = CADSpecs(**raw)
        except ValidationError:
            specs = CADSpecs(**{k: v for k, v in raw.items() if k in CADSpecs.__fields__})

        # ✅ Use relative path so it works both locally and in Docker
        output_dir = os.environ.get("OUTPUT_DIR", "outputs")
        os.makedirs(output_dir, exist_ok=True)
        safe = specs.part_name.replace(" ", "_").replace("/", "_")[:50] or "part"

        # DXF generation — rich geometry representing a valve
        try:
            dxf_path = f"{output_dir}/{safe}_2D.dxf"
            doc = ezdxf.new("R2018")
            doc.header["$INSUNITS"] = 4
            msp = doc.modelspace()

            l, w, h = specs.length_mm, specs.width_mm, specs.height_mm

            # ✅ Outer body rectangle
            msp.add_lwpolyline(
                [(0, 0), (l, 0), (l, w), (0, w), (0, 0)],
                close=True,
                dxfattribs={"layer": "BODY"}
            )

            # ✅ Valve bore circle (main cylinder)
            bore_radius = min(l, w) * 0.15
            center_x = l / 2
            center_y = w / 2
            msp.add_circle(
                center=(center_x, center_y),
                radius=bore_radius,
                dxfattribs={"layer": "BORE"}
            )

            # ✅ Inlet pipe circle (left)
            pipe_radius = bore_radius * 0.6
            msp.add_circle(
                center=(0, center_y),
                radius=pipe_radius,
                dxfattribs={"layer": "INLET"}
            )

            # ✅ Outlet pipe circle (right)
            msp.add_circle(
                center=(l, center_y),
                radius=pipe_radius,
                dxfattribs={"layer": "OUTLET"}
            )

            # ✅ Flange rectangles (top and bottom)
            flange_w = l * 0.2
            flange_h = w * 0.15

            msp.add_lwpolyline(
                [
                    (center_x - flange_w/2, w),
                    (center_x + flange_w/2, w),
                    (center_x + flange_w/2, w + flange_h),
                    (center_x - flange_w/2, w + flange_h),
                    (center_x - flange_w/2, w)
                ],
                close=True,
                dxfattribs={"layer": "FLANGE"}
            )

            msp.add_lwpolyline(
                [
                    (center_x - flange_w/2, 0),
                    (center_x + flange_w/2, 0),
                    (center_x + flange_w/2, -flange_h),
                    (center_x - flange_w/2, -flange_h),
                    (center_x - flange_w/2, 0)
                ],
                close=True,
                dxfattribs={"layer": "FLANGE"}
            )

            # ✅ Part label
            msp.add_text(
                f"{specs.part_name} | {specs.material} | {specs.pressure}",
                height=5.0,
                dxfattribs={"layer": "TEXT"}
            )

            doc.saveas(dxf_path)
            cad_paths.append(dxf_path)

        except Exception as e:
            errors.append(f"M2 DXF: {e}")

        # IFC generation
        try:
            ifc_path = f"{output_dir}/{safe}_3D.ifc"
            f = ifcopenshell.file(schema="IFC4")
            proj = f.createIfcProject(ifcopenshell.guid.new(), Name="Industrie IA")
            elem = f.createIfcBuildingElementProxy(
                ifcopenshell.guid.new(),
                Name=specs.part_name
            )
            f.createIfcRelAggregates(
                ifcopenshell.guid.new(),
                RelatingObject=proj,
                RelatedObjects=[elem]
            )
            f.write(ifc_path)
            cad_paths.append(ifc_path)

        except Exception as e:
            errors.append(f"M2 IFC: {e}")

        return {"cad_paths": cad_paths, "errors": errors}

    except Exception as e:
        return {"cad_paths": cad_paths, "errors": errors + [f"M2: {e}"]}