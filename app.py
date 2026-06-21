import io
import tempfile
import zipfile

import numpy as np
import streamlit as st
import trimesh


# ---------- Cherry MX dimensions ----------

TOP_OUTPUT = "clicker_top.stl"
BOTTOM_OUTPUT = "clicker_bottom.stl"

HOUSING_SIZE = 16.0
HOUSING_DEPTH = 5.2
CENTER_BOSS_SIZE = 7.0

CROSS_WIDTH = 4.20
CROSS_ARM = 1.45
CROSS_DEPTH = 4.2

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


# ---------- Helpers ----------

def load_mesh_from_upload(uploaded_file) -> trimesh.Trimesh:
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


def make_box(x, y, z, center):
    b = trimesh.creation.box(extents=[x, y, z])
    b.apply_translation(center)
    return b


def make_cylinder(diameter, height, center):
    c = trimesh.creation.cylinder(
        radius=diameter / 2,
        height=height,
        sections=48,
    )
    c.apply_translation(center)
    return c


def export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    data = mesh.export(file_type="stl")
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def make_zip_bytes(top_mesh: trimesh.Trimesh, bottom_mesh: trimesh.Trimesh) -> bytes:
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(TOP_OUTPUT, export_stl_bytes(top_mesh))
        z.writestr(BOTTOM_OUTPUT, export_stl_bytes(bottom_mesh))

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def apply_scale_about_center(mesh: trimesh.Trimesh, scale: float) -> trimesh.Trimesh:
    result = mesh.copy()
    center = result.bounds.mean(axis=0)
    result.apply_translation(-center)
    result.apply_scale(scale)
    result.apply_translation(center)
    return result


def generate_clicker_parts(mesh: trimesh.Trimesh, slice_z: float):
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

    if top_mesh is None or top_mesh.is_empty:
        raise ValueError("Top slice failed. Move the slice plane lower.")

    if bottom_mesh is None or bottom_mesh.is_empty:
        raise ValueError("Bottom slice failed. Move the slice plane higher.")

    # ---------- Top half cuts ----------

    top_result = top_mesh

    top_cut_z = slice_z + HOUSING_DEPTH / 2
    side_width = (HOUSING_SIZE - CENTER_BOSS_SIZE) / 2

    top_cutters = [
        make_box(side_width, HOUSING_SIZE, HOUSING_DEPTH, [
            mesh_center[0] - CENTER_BOSS_SIZE / 2 - side_width / 2,
            mesh_center[1],
            top_cut_z,
        ]),
        make_box(side_width, HOUSING_SIZE, HOUSING_DEPTH, [
            mesh_center[0] + CENTER_BOSS_SIZE / 2 + side_width / 2,
            mesh_center[1],
            top_cut_z,
        ]),
        make_box(CENTER_BOSS_SIZE, side_width, HOUSING_DEPTH, [
            mesh_center[0],
            mesh_center[1] + CENTER_BOSS_SIZE / 2 + side_width / 2,
            top_cut_z,
        ]),
        make_box(CENTER_BOSS_SIZE, side_width, HOUSING_DEPTH, [
            mesh_center[0],
            mesh_center[1] - CENTER_BOSS_SIZE / 2 - side_width / 2,
            top_cut_z,
        ]),
    ]

    for cutter in top_cutters:
        top_result = top_result.difference(cutter)

    cross_z = slice_z + CROSS_DEPTH / 2

    vertical_cross = make_box(
        CROSS_ARM,
        CROSS_WIDTH,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    horizontal_cross = make_box(
        CROSS_WIDTH,
        CROSS_ARM,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    top_result = top_result.difference(vertical_cross)
    top_result = top_result.difference(horizontal_cross)

    # ---------- Bottom half cuts ----------

    bottom_result = bottom_mesh

    bottom_cavity_z = slice_z - BOTTOM_CAVITY_DEPTH / 2

    bottom_cavity = make_box(
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_DEPTH,
        [mesh_center[0], mesh_center[1], bottom_cavity_z],
    )

    bottom_result = bottom_result.difference(bottom_cavity)

    hole_z = slice_z - HOLE_DEPTH / 2

    for x, y, dia in PIN_HOLES:
        hole = make_cylinder(
            dia,
            HOLE_DEPTH,
            [mesh_center[0] + x, mesh_center[1] + y, hole_z],
        )
        bottom_result = bottom_result.difference(hole)

    return top_result, bottom_result


# ---------- Streamlit UI ----------

st.set_page_config(
    page_title="STL to Cherry MX Clicker",
    layout="centered",
)

st.title("STL to Cherry MX Clicker")
st.write("Minimal version: upload an STL, choose scale and slice height, then generate top and bottom STL files.")

uploaded_file = st.file_uploader("Upload STL", type=["stl"])

if uploaded_file is None:
    st.info("Upload an STL to begin.")
    st.stop()

try:
    original_mesh = load_mesh_from_upload(uploaded_file)
except Exception as exc:
    st.error(f"Could not load STL: {exc}")
    st.stop()

scale = st.slider(
    "Scale",
    min_value=0.10,
    max_value=5.00,
    value=1.00,
    step=0.01,
)

mesh = apply_scale_about_center(original_mesh, scale)

bounds = mesh.bounds
zmin = float(bounds[0][2])
zmax = float(bounds[1][2])
default_slice = float((zmin + zmax) / 2)

st.write(
    f"Scaled model bounds: "
    f"{bounds[1][0] - bounds[0][0]:.2f} × "
    f"{bounds[1][1] - bounds[0][1]:.2f} × "
    f"{bounds[1][2] - bounds[0][2]:.2f} mm"
)

slice_z = st.slider(
    "Slice Z height",
    min_value=zmin,
    max_value=zmax,
    value=default_slice,
    step=max((zmax - zmin) / 200, 0.001),
)

top_space = zmax - slice_z
bottom_space = slice_z - zmin

top_needed = max(HOUSING_DEPTH, CROSS_DEPTH)
bottom_needed = max(BOTTOM_CAVITY_DEPTH, HOLE_DEPTH)

if top_space < top_needed:
    st.warning("Slice plane may be too high. The top cavity may cut through the model.")

if bottom_space < bottom_needed:
    st.warning("Slice plane may be too low. The bottom cavity or pin holes may cut through the model.")

st.write(f"Using slice Z: `{slice_z:.3f}`")

if st.button("Generate clicker STLs"):
    with st.spinner("Generating top and bottom STLs..."):
        try:
            top_result, bottom_result = generate_clicker_parts(mesh, slice_z)

            st.success("Generated successfully.")

            st.write("Top watertight:", top_result.is_watertight)
            st.write("Bottom watertight:", bottom_result.is_watertight)
            st.write("Top faces:", len(top_result.faces))
            st.write("Bottom faces:", len(bottom_result.faces))

            st.download_button(
                "Download both STLs as ZIP",
                data=make_zip_bytes(top_result, bottom_result),
                file_name="clicker_parts.zip",
                mime="application/zip",
            )

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "Download top STL only",
                    data=export_stl_bytes(top_result),
                    file_name=TOP_OUTPUT,
                    mime="model/stl",
                )

            with col2:
                st.download_button(
                    "Download bottom STL only",
                    data=export_stl_bytes(bottom_result),
                    file_name=BOTTOM_OUTPUT,
                    mime="model/stl",
                )

        except Exception as exc:
            st.error(f"Generation failed: {exc}")
            st.info("Try a simpler/watertight STL, a different slice height, or a slightly different scale.")
