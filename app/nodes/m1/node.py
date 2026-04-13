
import os
import re
import pdfplumber
import fitz
import pytesseract
from PIL import Image

from app.llm import llm_extract


# =========================
# 1. PDF TEXT EXTRACTION
# =========================
def extract_pdf_text(path: str) -> str:
    text = ""

    if not path or not os.path.exists(path):
        return ""

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
# 2. OCR FALLBACK
# =========================
def extract_ocr_text(path: str) -> str:
    text = ""

    if not path or not os.path.exists(path):
        return ""

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
# 3. SMART TEXT
# =========================
def get_full_text(path: str) -> str:
    text = extract_pdf_text(path)

    if len(text.strip()) < 50:
        print("⚠️ OCR fallback activated")
        text = extract_ocr_text(path)

    return text


# =========================
# 4. CLEANING FUNCTION
# =========================
def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# 🔥 NORMALIZATION CORE (ADDED)
# =========================
def normalize_value(v: str) -> str:
    v = v.lower().strip()

    # normalize industrial tags
    v = re.sub(r"\bdn\s*", "DN", v)
    v = re.sub(r"\bpn\s*", "PN", v)
    v = re.sub(r"api\s*", "API ", v)
    v = re.sub(r"iso\s*", "ISO ", v)
    v = re.sub(r"en\s*", "EN ", v)

    v = re.sub(r"\s+", " ", v)
    return v.strip()


def strong_dedup(lst):
    seen = set()
    out = []

    for x in lst:
        if not x:
            continue
        nx = normalize_value(x)
        if nx not in seen:
            seen.add(nx)
            out.append(nx)

    return out


def filter_temperatures(temps: list) -> list:
    valid = []

    for t in temps:
        match = re.search(r"-?\d+", t)
        if not match:
            continue

        value = int(match.group())

        # industrial realistic range
        if -100 <= value <= 600:
            valid.append(f"{value}°C")

    return sorted(list(set(valid)))


# =========================
# 5. REGEX EXTRACTION (IMPROVED)
# =========================
def parse_all_specs(text: str) -> dict:

    text = text.lower()

    dn = list(set(re.findall(r"dn\s?\d+", text)))
    pn = list(set(re.findall(r"pn\s?\d+", text)))

    materials = list(set(re.findall(
        r"(inox|stainless steel|steel|carbon steel|cast iron|aluminium|brass|inconel|cf8m|cf3m|wcb)",
        text
    )))

    temperatures = filter_temperatures(
        re.findall(r"-?\d+\s?°c", text)
    )

    fluids = list(set(re.findall(
        r"(water|steam|oil|gas|air|petroleum|hydrocarbon|fuel)",
        text
    )))

    certifications = list(set(re.findall(
        r"(atex|sil2|sil3|api\s?\d+|iso\s?\d+|en\s?\d+|ta-luft)",
        text
    )))

    valve_types = []
    if "butterfly" in text:
        valve_types.append("double offset butterfly valve")

    return {
        "diameters": strong_dedup(dn),
        "pressures": strong_dedup(pn),
        "materials": strong_dedup(materials),
        "temperatures": temperatures,
        "fluids": strong_dedup(fluids),
        "certifications": strong_dedup(certifications),
        "valve_types": strong_dedup(valve_types)
    }


# =========================
# 6. LLM EXTRACTION (STRICT JSON)
# =========================
def extract_specs_llm(text: str) -> dict:

    prompt = f"""
You are an industrial mechanical engineer.

Extract structured industrial specifications.

Return STRICT JSON ONLY.

Rules:
- NO explanation
- ONLY valid JSON
- Extract ALL values present

Schema:
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
{text[:4000]}
"""

    return llm_extract(prompt, mode="json")


# =========================
# 7. NORMALIZATION FUNCTION
# =========================
def normalize_specs(specs: dict) -> dict:

    def clean_list(lst):
        return strong_dedup(lst)

    return {
        "diameters": clean_list(specs.get("diameters", [])),
        "pressures": clean_list(specs.get("pressures", [])),
        "materials": clean_list(specs.get("materials", [])),
        "temperatures": filter_temperatures(specs.get("temperatures", [])),
        "fluids": clean_list(specs.get("fluids", [])),
        "certifications": clean_list(specs.get("certifications", [])),
        "valve_types": clean_list(specs.get("valve_types", []))
    }


# =========================
# 8. MAIN LANGGRAPH NODE
# =========================
def extract_specs(state: dict):
    
    try:
        input_file = state.get("input_file")
        input_prompt = state.get("input_prompt", "")

        # 1. Extract text
        pdf_text = get_full_text(input_file)
        full_text = clean_text(pdf_text + " " + input_prompt)

        # 2. LLM extraction
        specs = extract_specs_llm(full_text)

        # 3. fallback regex if LLM fails
        if not specs or not any(specs.values()):
            specs = parse_all_specs(full_text)

        # 4. normalization (IMPORTANT)
        specs = normalize_specs(specs)

        # 5. ✅ FIX: inject into state (SANS CHANGER TA LOGIQUE)
        state["M1_result"] = {
            "input_file": input_file,
            "input_prompt": input_prompt,
            "extracted_text_length": len(full_text),
            "specs": specs,
            "metadata": {
                "source": "pdf+ocr+llm",
                "confidence": "high"
            }
        }

        return state

    except Exception as e:
        state["M1_result"] = {}
        state["error"] = str(e)
        return state

