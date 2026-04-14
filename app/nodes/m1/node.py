import os
import re
import json
from datetime import datetime

from typing import Dict, Any   # 🔥 FIX IMPORTANT

import pdfplumber
import fitz
import pytesseract
from PIL import Image

from app.llm import get_llm


# =========================
# PDF TEXT EXTRACTION
# =========================
def extract_pdf_text(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""

    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except:
        pass

    return text


# =========================
# OCR FALLBACK
# =========================
def extract_ocr_text(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""

    text = ""
    try:
        doc = fitz.open(path)
        for page in doc:
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img) + "\n"
    except:
        pass

    return text


# =========================
# FULL TEXT
# =========================
def get_full_text(path: str) -> str:
    text = extract_pdf_text(path)
    if len(text.strip()) < 50:
        text += extract_ocr_text(path)
    return text


# =========================
# CLEAN TEXT
# =========================
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# =========================
# SAFE LLM EXTRACTION
# =========================
def extract_specs_llm(text: str) -> dict:

    llm = get_llm()

    prompt = f"""
Extract industrial specs from text.

Return ONLY valid JSON:
{{
  "diameters": [],
  "pressures": [],
  "materials": [],
  "temperatures": [],
  "fluids": [],
  "certifications": [],
  "valve_types": []
}}

TEXT:
{text[:3000]}
"""

    try:
        res = llm.invoke(prompt)
        content = res.content.strip()
        return json.loads(content)
    except:
        return {}


# =========================
# REGEX FALLBACK
# =========================
def parse_all_specs(text: str) -> dict:

    text = text.lower()

    return {
        "diameters": list(set(re.findall(r"\bdn\s?\d+\b", text))),
        "pressures": list(set(re.findall(r"\bpn\s?\d+\b", text))),
        "materials": list(set(re.findall(r"(inox|steel|carbon steel|cast iron|aluminium|brass|inconel|cf8m|cf3m|wcb)", text))),
        "temperatures": list(set(re.findall(r"-?\d+\s?°c", text))),
        "fluids": list(set(re.findall(r"(water|steam|oil|gas|air)", text))),
        "certifications": list(set(re.findall(r"(atex|sil2|sil3|api\s?\d+|iso\s?\d+)", text))),
        "valve_types": ["butterfly valve"] if "butterfly" in text else []
    }


# =========================
# NORMALIZE (CLEAN ONLY)
# =========================
def normalize_specs(specs: dict) -> dict:

    def clean_list(lst):
        if not lst:
            return []
        return list(set([str(x).lower().strip() for x in lst]))

    diameters = []
    for d in specs.get("diameters", []):
        nums = re.findall(r"\d+", d)
        if nums:
            diameters.append(f"dn{int(nums[0])}")

    pressures = []
    for p in specs.get("pressures", []):
        nums = re.findall(r"\d+", p)
        if nums:
            pressures.append(f"pn{int(nums[0])}")

    temperatures = []
    for t in specs.get("temperatures", []):
        nums = re.findall(r"-?\d+", t)
        for n in nums:
            temperatures.append(f"{int(n)}°c")

    materials = clean_list(specs.get("materials", []))

    certifications = []
    for c in specs.get("certifications", []):
        certifications.append(c.lower().replace(" ", ""))

    return {
        "diameters": sorted(list(set(diameters))),
        "pressures": sorted(list(set(pressures))),
        "materials": sorted(list(set(materials))),
        "temperatures": sorted(list(set(temperatures))),
        "fluids": sorted(list(set(clean_list(specs.get("fluids", []))))),
        "certifications": sorted(list(set(certifications))),
        "valve_types": sorted(list(set(clean_list(specs.get("valve_types", [])))))
    }


# =========================
# NODE M1
# =========================
def extract_specs(state: dict):

    try:
        file = state.get("input_file")
        prompt = state.get("input_prompt", "")

        text = clean_text(get_full_text(file) + " " + prompt)

        specs = extract_specs_llm(text)

        if not specs or not any(specs.values()):
            specs = parse_all_specs(text)

        specs = normalize_specs(specs)

        state["M1_result"] = {
            "input_file": file,
            "input_prompt": prompt,
            "text_length": len(text),
            "specs": specs,
            "metadata": {
                "source": "pdf+ocr+llm",
                "confidence": "high"
            }
        }

        os.makedirs("outputs", exist_ok=True)
        path = f"outputs/M1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(path, "w") as f:
            json.dump(state["M1_result"], f, indent=2)

        state["M1_result"]["output_file"] = path

        return state

    except Exception as e:
        state["M1_result"] = {}
        state["error"] = str(e)
        return state


# =========================
# SAVE OUTPUT FUNCTION (OK)
# =========================
def save_output(state: Dict[str, Any]) -> str:

    try:
        os.makedirs("outputs", exist_ok=True)

        filename = f"M4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join("outputs", filename)

        output_data = {
            "M1_result": state.get("M1_result", {}),
            "M4_result": state.get("M4_result", []),
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return path

    except Exception as e:
        print("❌ SAVE ERROR:", e)
        return ""


# =========================
# EXPORT NODE
# =========================
m1_node = extract_specs