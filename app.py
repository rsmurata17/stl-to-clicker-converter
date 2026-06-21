import io
import tempfile
from pathlib import Path

import numpy as np
import streamlit as st
import trimesh


# ---------- CONSTANTS ----------

TOP_OUTPUT = "clicker_top.stl"
BOTTOM_OUTPUT = "clicker_bottom.stl"

# Top half: MX stem + top housing
HOUSING_SIZE = 16.0
HOUSING_DEPTH = 5.2
CENTER_BOSS_SIZE = 7.0
CROSS_WIDTH = 4.20
CROSS_ARM = 1.45
CROSS_DEPTH = 4.2

# Bottom half: switch body + pin holes
BOTTOM_CAVITY_SIZE = 16.0
BOTTOM_CAVITY_DEPTH = 5.2
CENTER_HOLE_DIA = 4.00
FIXATION_PIN_DIA = 1.80
CONTACT_PIN_DIA = 1.60
HOLE_DEPTH = BOTTOM_CAVITY_DEPTH + 5.0

GRID = 1.27

PIN_HOLES = [
    (0.00, 0.00, CENTER_HOLE_DIA),
    (-4 * GRID, 0.00, FIXATION_PIN_DIA),
    (4 * GRID, 0.00, FIXATION_PIN_DIA),
    (-3 * GRID, 2 * GRID, CONTACT_PIN_DIA),
    (2 * GRID, 4 * GRID, CONTACT_PIN_DIA),
]


# ---------- HELPERS ----------

def load_mesh_from_bytes(file_bytes: bytes) -> trimesh.Trimesh:
    mesh = trimesh.load(io.BytesIO(file_bytes), file_type="stl")

    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("Could not load this STL as a mesh.")

    if mesh.faces is None or len(mesh.faces) == 0:
        raise ValueError("This STL does not contain any faces.")

    return mesh


def box(x: float, y: float, z: float, center) -> trimesh.Trimesh:
    b = trimesh.creation.box(extents=[x, y, z])
    b.apply_translation(center)
    return b


def cylinder(diameter: float, height: float, center) -> trimesh.Trimesh:
    c = trimesh.creation.cylinder(
        radius=diameter / 2,
        height=height,
        sections=48,
    )
    c.apply_translation(center)
    return c


def mesh_stats(mesh: trimesh.Trimesh) -> dict:
    bounds = mesh.bounds
    size = bounds[1] - bounds[0]

    return {
        "X size": float(size[0]),
        "Y size": float(size[1]),
        "Z size": float(size[2]),
        "Faces": int(len(mesh.faces)),
        "Watertight": bool(mesh.is_watertight),
    }


def export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    exported = mesh.export(file_type="stl")

    if isinstance(exported, str):
        return exported.encode("utf-8")

    return exported


def make_clicker_parts(input_mesh: trimesh.Trimesh, scale_factor: float, slice_z: float):
    mesh = input_mesh.copy()

    mesh_center = mesh.bounds.mean(axis=0)

    mesh.apply_translation(-mesh_center)
    mesh.apply_scale(scale_factor)
    mesh.apply_translation(mesh_center)

    mesh_center = mesh.bounds.mean(axis=0)

    top_mesh = mesh.slice_plane(
        plane_origin=[0, 0, slice_z],
        plane_normal=[0, 0, 1],
        cap=True,
    )

    bottom_mesh = mesh.slice_plane(
        plane_origin=[0, 0, slice_z],
        plane_normal=[0, 0, -1],
        cap=True,
    )

    if top_mesh is None or bottom_mesh is None:
        raise ValueError("Slice failed. Try a different slice Z height.")

    # ---------- CUT TOP HALF ----------

    top_result = top_mesh

    top_cut_z = slice_z + HOUSING_DEPTH / 2
    side_width = (HOUSING_SIZE - CENTER_BOSS_SIZE) / 2

    top_cutters = [
        box(side_width, HOUSING_SIZE, HOUSING_DEPTH, [
            mesh_center[0] - CENTER_BOSS_SIZE / 2 - side_width / 2,
            mesh_center[1],
            top_cut_z,
        ]),
        box(side_width, HOUSING_SIZE, HOUSING_DEPTH, [
            mesh_center[0] + CENTER_BOSS_SIZE / 2 + side_width / 2,
            mesh_center[1],
            top_cut_z,
        ]),
        box(CENTER_BOSS_SIZE, side_width, HOUSING_DEPTH, [
            mesh_center[0],
            mesh_center[1] + CENTER_BOSS_SIZE / 2 + side_width / 2,
            top_cut_z,
        ]),
        box(CENTER_BOSS_SIZE, side_width, HOUSING_DEPTH, [
            mesh_center[0],
            mesh_center[1] - CENTER_BOSS_SIZE / 2 - side_width / 2,
            top_cut_z,
        ]),
    ]

    for cutter in top_cutters:
        top_result = top_result.difference(cutter)

    cross_z = slice_z + CROSS_DEPTH / 2

    vertical_cross = box(
        CROSS_ARM,
        CROSS_WIDTH,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    horizontal_cross = box(
        CROSS_WIDTH,
        CROSS_ARM,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    top_result = top_result.difference(vertical_cross)
    top_result = top_result.difference(horizontal_cross)

    # ---------- CUT BOTTOM HALF ----------

    bottom_result = bottom_mesh

    bottom_cavity_z = slice_z - BOTTOM_CAVITY_DEPTH / 2

    bottom_cavity = box(
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_DEPTH,
        [mesh_center[0], mesh_center[1], bottom_cavity_z],
    )

    bottom_result = bottom_result.difference(bottom_cavity)

    hole_z = slice_z - HOLE_DEPTH / 2

    for x, y, dia in PIN_HOLES:
        hole = cylinder(
            dia,
            HOLE_DEPTH,
            [
                mesh_center[0] + x,
                mesh_center[1] + y,
                hole_z,
            ],
        )
        bottom_result = bottom_result.difference(hole)

    return mesh, top_result, bottom_result


# ---------- STREAMLIT UI ----------

st.set_page_config(
    page_title="STL to Clicker Converter",
    page_icon="⌨️",
    layout="centered",
)

st.title("STL to Clicker Converter")
st.write(
    "Upload an STL, choose the scale and slice height, then generate top and bottom "
    "parts for a Cherry MX-style clicker."
)

uploaded_file = st.file_uploader("Upload STL file", type=["stl"])

if uploaded_file is None:
    st.info("Upload an STL to begin.")
    st.stop()

file_bytes = uploaded_file.read()

try:
    original_mesh = load_mesh_from_bytes(file_bytes)
except Exception as e:
    st.error(f"Could not load STL: {e}")
    st.stop()

original_stats = mesh_stats(original_mesh)
bounds = original_mesh.bounds
zmin, zmax = float(bounds[0][2]), float(bounds[1][2])
zmid = (zmin + zmax) / 2

st.subheader("Original STL")
col1, col2, col3 = st.columns(3)
col1.metric("X size", f"{original_stats['X size']:.2f} mm")
col2.metric("Y size", f"{original_stats['Y size']:.2f} mm")
col3.metric("Z size", f"{original_stats['Z size']:.2f} mm")

st.write(f"Faces: `{original_stats['Faces']}`")
st.write(f"Watertight: `{original_stats['Watertight']}`")

st.subheader("Settings")

scale_factor = st.slider(
    "Scale factor",
    min_value=0.10,
    max_value=5.00,
    value=1.00,
    step=0.01,
)

scaled_zmin = zmid + (zmin - zmid) * scale_factor
scaled_zmax = zmid + (zmax - zmid) * scale_factor
scaled_zmid = (scaled_zmin + scaled_zmax) / 2

slice_z = st.slider(
    "Slice Z height",
    min_value=float(scaled_zmin),
    max_value=float(scaled_zmax),
    value=float(scaled_zmid),
    step=max((scaled_zmax - scaled_zmin) / 500, 0.01),
)

top_space = scaled_zmax - slice_z
bottom_space = slice_z - scaled_zmin

top_needed = max(HOUSING_DEPTH, CROSS_DEPTH)
bottom_needed = max(BOTTOM_CAVITY_DEPTH, HOLE_DEPTH)

if top_space < top_needed:
    st.warning("Slice plane may be too high. The top cavity may cut through the model.")

if bottom_space < bottom_needed:
    st.warning("Slice plane may be too low. The bottom cavity or pin holes may cut through the model.")

st.subheader("Generate")

if st.button("Generate clicker STL files"):
    try:
        scaled_mesh, top_result, bottom_result = make_clicker_parts(
            original_mesh,
            scale_factor,
            slice_z,
        )

        top_bytes = export_stl_bytes(top_result)
        bottom_bytes = export_stl_bytes(bottom_result)

        st.success("Generated top and bottom STL files.")

        top_stats = mesh_stats(top_result)
        bottom_stats = mesh_stats(bottom_result)

        st.write("### Output stats")
        st.write(
            {
                "Top watertight": top_stats["Watertight"],
                "Bottom watertight": bottom_stats["Watertight"],
                "Top faces": top_stats["Faces"],
                "Bottom faces": bottom_stats["Faces"],
            }
        )

        st.download_button(
            "Download clicker_top.stl",
            data=top_bytes,
            file_name=TOP_OUTPUT,
            mime="model/stl",
        )

        st.download_button(
            "Download clicker_bottom.stl",
            data=bottom_bytes,
            file_name=BOTTOM_OUTPUT,
            mime="model/stl",
        )

    except Exception as e:
        st.error(
            "Generation failed. This usually means the STL or boolean operation failed. "
            "Try a different slice height or a simpler/watertight STL."
        )
        st.exception(e)
