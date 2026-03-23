"""
app/services/vehicle_service.py — Vehicle classifier.

Rule-based first (zero cost, zero hallucination, ~95% coverage for Morocco).
Future: augment with an LLM classify_vehicle tool call for unknowns.
"""
from app.core.logging import get_logger

logger = get_logger(__name__)

# Known vehicle model → category mappings for the Moroccan market
VEHICLE_DB: dict[str, str] = {
    # Citadine
    "picanto": "citadine", "kia picanto": "citadine",
    "i10": "citadine", "hyundai i10": "citadine",
    "i20": "citadine", "hyundai i20": "citadine",
    "clio": "citadine", "renault clio": "citadine",
    "twingo": "citadine", "renault twingo": "citadine",
    "vitz": "citadine", "yaris": "citadine", "toyota yaris": "citadine",
    "spark": "citadine", "chevrolet spark": "citadine",
    "polo": "citadine", "volkswagen polo": "citadine",
    "sandero": "citadine", "dacia sandero": "citadine",
    "205": "citadine", "peugeot 205": "citadine",
    "206": "citadine", "peugeot 206": "citadine",
    "208": "citadine", "peugeot 208": "citadine",
    "aygo": "citadine", "toyota aygo": "citadine",
    "saxo": "citadine", "citroen saxo": "citadine",
    "c1": "citadine", "citroen c1": "citadine",
    "up": "citadine", "volkswagen up": "citadine",
    "kwid": "citadine", "renault kwid": "citadine",

    # Berline
    "logan": "berline", "dacia logan": "berline",
    "corolla": "berline", "toyota corolla": "berline",
    "elantra": "berline", "hyundai elantra": "berline",
    "accent": "berline", "hyundai accent": "berline",
    "rio": "berline", "kia rio": "berline",
    "cerato": "berline", "kia cerato": "berline",
    "megane": "berline", "renault megane": "berline",
    "301": "berline", "peugeot 301": "berline",
    "308": "berline", "peugeot 308": "berline",
    "408": "berline", "peugeot 408": "berline",
    "civic": "berline", "honda civic": "berline",
    "accord": "berline", "honda accord": "berline",
    "camry": "berline", "toyota camry": "berline",
    "golf": "berline", "volkswagen golf": "berline",
    "jetta": "berline", "volkswagen jetta": "berline",
    "passat": "berline", "volkswagen passat": "berline",
    "308 sw": "berline",
    "laguna": "berline", "renault laguna": "berline",
    "508": "berline", "peugeot 508": "berline",
    "fluence": "berline", "renault fluence": "berline",

    # SUV / 4x4
    "duster": "suv", "dacia duster": "suv",
    "mage": "suv", "dongfeng mage": "suv", "dongfeng": "suv",
    "tucson": "suv", "hyundai tucson": "suv",
    "sportage": "suv", "kia sportage": "suv",
    "rav4": "suv", "toyota rav4": "suv",
    "cr-v": "suv", "honda crv": "suv", "honda cr-v": "suv",
    "cx-5": "suv", "mazda cx5": "suv", "mazda cx-5": "suv",
    "patrol": "suv", "nissan patrol": "suv",
    "x-trail": "suv", "nissan x-trail": "suv",
    "q5": "suv", "audi q5": "suv",
    "q7": "suv", "audi q7": "suv",
    "x5": "suv", "bmw x5": "suv",
    "santa fe": "suv", "hyundai santa fe": "suv",
    "trailblazer": "suv",
    "cherokee": "suv", "jeep cherokee": "suv",
    "defender": "suv", "land rover defender": "suv",
    "discovery": "suv", "land rover discovery": "suv",
    "fortuner": "suv", "toyota fortuner": "suv",
    "hilux": "suv", "toyota hilux": "suv",
    "navara": "suv", "nissan navara": "suv",
    "haval h6": "suv", "haval": "suv",
    "jetour": "suv",
}


def classify_vehicle(vehicle_text: str) -> dict:
    """
    Classify a vehicle from free text to a category.

    Returns:
        {"category": str | None, "confidence": float, "matched_key": str | None}
    """
    if not vehicle_text:
        return {"category": None, "confidence": 0.0, "matched_key": None}

    normalized = vehicle_text.strip().lower()

    # Exact match
    if normalized in VEHICLE_DB:
        return {"category": VEHICLE_DB[normalized], "confidence": 1.0, "matched_key": normalized}

    # Partial match — find the first key that appears in the input
    for key, category in VEHICLE_DB.items():
        if key in normalized or normalized in key:
            return {"category": category, "confidence": 0.85, "matched_key": key}

    # No match — ask the caller to escalate or ask the customer
    logger.info("vehicle_classify_miss", vehicle_text=vehicle_text)
    return {"category": None, "confidence": 0.0, "matched_key": None}
