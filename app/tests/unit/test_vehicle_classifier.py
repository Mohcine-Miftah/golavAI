"""
app/tests/unit/test_vehicle_classifier.py
"""
import pytest

from app.services.vehicle_service import classify_vehicle


@pytest.mark.parametrize("text,expected_category", [
    ("Logan", "berline"),
    ("dacia logan", "berline"),
    ("Duster", "suv"),
    ("DACIA DUSTER", "suv"),
    ("Picanto", "citadine"),
    ("Kia Picanto", "citadine"),
    ("Honda CRV", "suv"),
    ("honda cr-v", "suv"),
    ("Dongfeng Mage", "suv"),
    ("Clio", "citadine"),
    ("Hyundai Tucson", "suv"),
])
def test_classify_known_vehicles(text, expected_category):
    result = classify_vehicle(text)
    assert result["category"] == expected_category
    assert result["confidence"] > 0


def test_classify_unknown_vehicle():
    result = classify_vehicle("XYZ9000 Concept")
    assert result["category"] is None
    assert result["confidence"] == 0.0


def test_classify_empty_string():
    result = classify_vehicle("")
    assert result["category"] is None
