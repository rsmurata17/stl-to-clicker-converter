import tempfile
from typing import Any

import numpy as np
import trimesh


def load_mesh_from_upload(uploaded_file: Any) -> trimesh.Trimesh:
    """Load a Streamlit-uploaded STL file as a single Trimesh."""
    data = uploaded_file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".stl") as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    mesh = trimesh.load(tmp_path)
    if not isinstance(mesh, trimesh.Trimesh):
        mesh = mesh.dump(concatenate=True)
    if mesh.is_empty:
        raise ValueError("The uploaded STL is empty.")
    return mesh


def make_box(x: float, y: float, z: float, center) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=[x, y, z])
    mesh.apply_translation(center)
    return mesh


def make_cylinder(diameter: float, height: float, center, sections: int = 72) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=diameter / 2, height=height, sections=sections)
    mesh.apply_translation(center)
    return mesh


def apply_scale_about_center(mesh: trimesh.Trimesh, scale: float) -> trimesh.Trimesh:
    result = mesh.copy()
    center = result.bounds.mean(axis=0)
    result.apply_translation(-center)
    result.apply_scale(scale)
    result.apply_translation(center)
    return result


def safe_boolean_difference(base: trimesh.Trimesh, cutter: trimesh.Trimesh, label: str) -> trimesh.Trimesh:
    """Run a boolean difference with a useful user-facing error message."""
    try:
        result = base.difference(cutter)
    except ModuleNotFoundError as exc:
        missing = exc.name or str(exc)
        raise RuntimeError(
            f"Boolean/slicing dependency is missing: {missing}. Add it to requirements.txt, "
            "then redeploy Streamlit."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Boolean cut failed while cutting {label}. Make sure requirements.txt includes "
            f"manifold3d and try a simpler/watertight STL. Original error: {exc}"
        ) from exc

    if result is None or result.is_empty:
        raise RuntimeError(f"Boolean cut produced an empty mesh while cutting {label}.")
    return result


def decimate_for_preview(mesh: trimesh.Trimesh, max_faces: int = 14000) -> trimesh.Trimesh:
    if len(mesh.faces) <= max_faces:
        return mesh
    face_indices = np.linspace(0, len(mesh.faces) - 1, max_faces).astype(int)
    return mesh.submesh([face_indices], append=True, repair=False)
