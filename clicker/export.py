"""
STL and ZIP export helpers.
"""

import io
import re
import zipfile

import trimesh

from .config import APP_VERSION


def export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def clean_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return "clicker"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._-")
    return name or "clicker"


def make_zip_bytes(top_mesh: trimesh.Trimesh, bottom_mesh: trimesh.Trimesh, base_name: str) -> bytes:
    top_name = f"{base_name}_top.stl"
    bottom_name = f"{base_name}_bottom.stl"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(top_name, export_stl_bytes(top_mesh))
        zf.writestr(bottom_name, export_stl_bytes(bottom_mesh))
        zf.writestr(
            f"{base_name}_generation_report.txt",
            "\n".join([
                f"App version: {APP_VERSION}",
                f"Top file: {top_name}",
                f"Bottom file: {bottom_name}",
                f"Top watertight: {top_mesh.is_watertight}",
                f"Bottom watertight: {bottom_mesh.is_watertight}",
                f"Top faces: {len(top_mesh.faces)}",
                f"Bottom faces: {len(bottom_mesh.faces)}",
            ]),
        )
    buffer.seek(0)
    return buffer.getvalue()
