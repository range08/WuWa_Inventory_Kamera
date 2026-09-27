"""Rover variant mapping derived from Global 3.6 main-role configuration."""

from __future__ import annotations


ROVER_GENDERS = ("Female", "Male")
ROVER_ELEMENTS = ("Spectro", "Havoc", "Aero", "Electro")

_ROVER_IDS = {
    ("Male", "Spectro"): "1501",
    ("Female", "Spectro"): "1502",
    ("Male", "Havoc"): "1605",
    ("Female", "Havoc"): "1604",
    ("Male", "Aero"): "1406",
    ("Female", "Aero"): "1408",
    ("Male", "Electro"): "1309",
    ("Female", "Electro"): "1310",
}


def resolve_rover_id(gender: str, element: str) -> str:
    try:
        return _ROVER_IDS[(gender, element)]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported Rover variant: gender={gender!r}, element={element!r}"
        ) from exc
