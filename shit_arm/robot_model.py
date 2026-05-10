from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


URDF_PATH = Path(__file__).parent / "assets" / "urdf" / "so101_new_calib.urdf"
JOINT_ORDER = {
    "shoulder_pan": 0,
    "shoulder_lift": 1,
    "elbow_flex": 2,
    "wrist_flex": 3,
    "wrist_roll": 4,
    "gripper": 5,
}


@lru_cache(maxsize=1)
def load_robot_model() -> dict[str, Any]:
    root = ElementTree.parse(URDF_PATH).getroot()
    materials = _materials_payload(root)
    return {
        "name": root.attrib.get("name", "robot"),
        "format": "urdf",
        "urdf_path": str(URDF_PATH),
        "asset_root": str(URDF_PATH.parent),
        "links": [_link_payload(link, materials) for link in root.findall("link")],
        "joints": sorted(
            [_joint_payload(joint) for joint in root.findall("joint")],
            key=lambda joint: (JOINT_ORDER.get(joint["name"], len(JOINT_ORDER)), joint["name"]),
        ),
    }


def _materials_payload(root: ElementTree.Element) -> dict[str, tuple[float, float, float, float]]:
    materials: dict[str, tuple[float, float, float, float]] = {}
    for material in root.findall("material"):
        name = material.attrib.get("name")
        color = _material_color(material)
        if name and color:
            materials[name] = color
    return materials


def _link_payload(
    link: ElementTree.Element,
    materials: dict[str, tuple[float, float, float, float]],
) -> dict[str, Any]:
    visuals = [_visual_payload(visual, materials) for visual in link.findall("visual")]
    return {
        "name": link.attrib["name"],
        "visual": visuals[0] if visuals else None,
        "visuals": visuals,
    }


def _joint_payload(joint: ElementTree.Element) -> dict[str, Any]:
    origin = joint.find("origin")
    axis = joint.find("axis")
    limit = joint.find("limit")
    parent = joint.find("parent")
    child = joint.find("child")
    return {
        "name": joint.attrib["name"],
        "type": joint.attrib.get("type", "fixed"),
        "parent": parent.attrib["link"] if parent is not None else None,
        "child": child.attrib["link"] if child is not None else None,
        "origin": {
            "xyz": _float_tuple(origin.attrib.get("xyz", "0 0 0")) if origin is not None else (0.0, 0.0, 0.0),
            "rpy": _float_tuple(origin.attrib.get("rpy", "0 0 0")) if origin is not None else (0.0, 0.0, 0.0),
        },
        "axis": _float_tuple(axis.attrib.get("xyz", "0 0 0")) if axis is not None else (0.0, 0.0, 0.0),
        "limit": {
            "lower": _float_attr(limit, "lower"),
            "upper": _float_attr(limit, "upper"),
            "effort": _float_attr(limit, "effort"),
            "velocity": _float_attr(limit, "velocity"),
        }
        if limit is not None
        else None,
    }


def _visual_payload(
    visual: ElementTree.Element,
    materials: dict[str, tuple[float, float, float, float]],
) -> dict[str, Any]:
    origin = visual.find("origin")
    geometry = visual.find("geometry")
    material = visual.find("material")
    return {
        "origin": {
            "xyz": _float_tuple(origin.attrib.get("xyz", "0 0 0")) if origin is not None else (0.0, 0.0, 0.0),
            "rpy": _float_tuple(origin.attrib.get("rpy", "0 0 0")) if origin is not None else (0.0, 0.0, 0.0),
        },
        "geometry": _geometry_payload(geometry) if geometry is not None else None,
        "color": _visual_color(material, materials),
    }


def _geometry_payload(geometry: ElementTree.Element) -> dict[str, Any] | None:
    box = geometry.find("box")
    cylinder = geometry.find("cylinder")
    sphere = geometry.find("sphere")
    mesh = geometry.find("mesh")
    if box is not None:
        return {"type": "box", "size": _float_tuple(box.attrib["size"])}
    if cylinder is not None:
        return {
            "type": "cylinder",
            "radius": float(cylinder.attrib["radius"]),
            "length": float(cylinder.attrib["length"]),
        }
    if sphere is not None:
        return {"type": "sphere", "radius": float(sphere.attrib["radius"])}
    if mesh is not None:
        payload: dict[str, Any] = {"type": "mesh", "filename": mesh.attrib["filename"]}
        if "scale" in mesh.attrib:
            payload["scale"] = _float_tuple(mesh.attrib["scale"])
        return payload
    return None


def _visual_color(
    material: ElementTree.Element | None,
    materials: dict[str, tuple[float, float, float, float]],
) -> tuple[float, float, float, float] | None:
    color = _material_color(material)
    if color:
        return color
    if material is None:
        return None
    name = material.attrib.get("name")
    return materials.get(name) if name else None


def _material_color(material: ElementTree.Element | None) -> tuple[float, float, float, float] | None:
    if material is None:
        return None
    color = material.find("color")
    if color is None:
        return None
    return _float_tuple(color.attrib["rgba"])  # type: ignore[return-value]


def _float_tuple(value: str) -> tuple[float, ...]:
    return tuple(float(part) for part in value.split())


def _float_attr(element: ElementTree.Element, name: str) -> float | None:
    value = element.attrib.get(name)
    return float(value) if value is not None else None
