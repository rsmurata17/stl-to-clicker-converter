import io
import tempfile
import zipfile

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import trimesh


# ---------- Cherry MX dimensions ----------

TOP_OUTPUT = "clicker_top.stl"
BOTTOM_OUTPUT = "clicker_bottom.stl"

HOUSING_SIZE = 16.0
HOUSING_DEPTH = 5.2
CENTER_BOSS_SIZE = 7.0

# Cross dimensions are the measured near-fit values, then clearance is added.
# Increase TOP_STEM_TOLERANCE if the printed stem still feels too tight.
CROSS_WIDTH = 4.20
CROSS_ARM = 1.45
CROSS_DEPTH = 4.2
TOP_STEM_TOLERANCE = 0.20

BOTTOM_CAVITY_SIZE = 16.0
BOTTOM_CAVITY_DEPTH = 5.2

# Center post clearance for the bottom half.
# Increase CENTER_HOLE_TOLERANCE if the switch center post still binds.
CENTER_HOLE_DIA = 4.00
CENTER_HOLE_TOLERANCE = 0.30

# Universal bottom cavity: keep a circular center support wall, remove the rest
# as one open pocket so different switch pin layouts can fit.
CENTER_SUPPORT_WALL = 1.40
UNIVERSAL_CAVITY_DEPTH = BOTTOM_CAVITY_DEPTH
HOLE_DEPTH = BOTTOM_CAVITY_DEPTH + 5.0


# ---------- Mesh helpers ----------

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
        z.writestr(
            "generation_report.txt",
            "\n".join([
                f"Top watertight: {top_mesh.is_watertight}",
                f"Bottom watertight: {bottom_mesh.is_watertight}",
                f"Top faces: {len(top_mesh.faces)}",
                f"Bottom faces: {len(bottom_mesh.faces)}",
            ]),
        )

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def apply_scale_about_center(mesh: trimesh.Trimesh, scale: float) -> trimesh.Trimesh:
    result = mesh.copy()
    center = result.bounds.mean(axis=0)
    result.apply_translation(-center)
    result.apply_scale(scale)
    result.apply_translation(center)
    return result


def decimate_for_preview(mesh: trimesh.Trimesh, max_faces: int = 12000) -> trimesh.Trimesh:
    """Keep browser preview responsive on dense STL files."""
    if len(mesh.faces) <= max_faces:
        return mesh

    sample_count = min(max_faces, len(mesh.faces))
    face_indices = np.linspace(0, len(mesh.faces) - 1, sample_count).astype(int)
    preview = mesh.submesh([face_indices], append=True, repair=False)
    return preview


# ---------- Plotly visualizer helpers ----------

def add_mesh_to_figure(
    fig: go.Figure,
    mesh: trimesh.Trimesh,
    name: str,
    opacity: float = 0.55,
):
    preview_mesh = decimate_for_preview(mesh)
    vertices = preview_mesh.vertices
    faces = preview_mesh.faces

    fig.add_trace(
        go.Mesh3d(
            x=vertices[:, 0],
            y=vertices[:, 1],
            z=vertices[:, 2],
            i=faces[:, 0],
            j=faces[:, 1],
            k=faces[:, 2],
            name=name,
            opacity=opacity,
            showscale=False,
        )
    )


def add_slice_plane_to_figure(fig: go.Figure, mesh: trimesh.Trimesh, slice_z: float):
    bounds = mesh.bounds
    xmin, ymin, _ = bounds[0]
    xmax, ymax, _ = bounds[1]

    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2

    x_size = max(xmax - xmin, 1.0) * 1.25
    y_size = max(ymax - ymin, 1.0) * 1.25

    x = np.array([cx - x_size / 2, cx + x_size / 2])
    y = np.array([cy - y_size / 2, cy + y_size / 2])

    xx, yy = np.meshgrid(x, y)
    zz = np.full_like(xx, slice_z)

    fig.add_trace(
        go.Surface(
            x=xx,
            y=yy,
            z=zz,
            name="Slice plane",
            opacity=0.35,
            showscale=False,
        )
    )


def add_mx_reference_cube(fig: go.Figure, center_xy, z_center: float, size: float = 19.0):
    cx, cy = center_xy
    half = size / 2

    points = np.array([
        [cx - half, cy - half, z_center - half],
        [cx + half, cy - half, z_center - half],
        [cx + half, cy + half, z_center - half],
        [cx - half, cy + half, z_center - half],
        [cx - half, cy - half, z_center + half],
        [cx + half, cy - half, z_center + half],
        [cx + half, cy + half, z_center + half],
        [cx - half, cy + half, z_center + half],
    ])

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]

    x, y, z = [], [], []
    for start, end in edges:
        x.extend([points[start, 0], points[end, 0], None])
        y.extend([points[start, 1], points[end, 1], None])
        z.extend([points[start, 2], points[end, 2], None])

    fig.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            name="19 mm Cherry MX reference cube",
            line=dict(width=5),
        )
    )


def make_input_preview_figure(mesh: trimesh.Trimesh, slice_z: float) -> go.Figure:
    fig = go.Figure()

    add_mesh_to_figure(fig, mesh, "Uploaded STL", opacity=0.55)
    add_slice_plane_to_figure(fig, mesh, slice_z)

    center = mesh.bounds.mean(axis=0)
    add_mx_reference_cube(fig, (center[0], center[1]), slice_z, size=19.0)

    fig.update_layout(
        height=650,
        scene=dict(
            aspectmode="data",
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h"),
    )

    return fig


def make_final_preview_figure(top_mesh: trimesh.Trimesh, bottom_mesh: trimesh.Trimesh) -> go.Figure:
    fig = go.Figure()

    top_preview = top_mesh.copy()
    bottom_preview = bottom_mesh.copy()

    # Separate the top from the bottom for easier visual inspection.
    z_gap = 8.0
    top_preview.apply_translation([0, 0, z_gap])

    add_mesh_to_figure(fig, top_preview, "Top half", opacity=0.8)
    add_mesh_to_figure(fig, bottom_preview, "Bottom half", opacity=0.8)

    fig.update_layout(
        height=650,
        scene=dict(
            aspectmode="data",
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h"),
    )

    return fig


# ---------- Clicker generation ----------

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
        CROSS_ARM + TOP_STEM_TOLERANCE,
        CROSS_WIDTH + TOP_STEM_TOLERANCE,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    horizontal_cross = make_box(
        CROSS_WIDTH + TOP_STEM_TOLERANCE,
        CROSS_ARM + TOP_STEM_TOLERANCE,
        CROSS_DEPTH,
        [mesh_center[0], mesh_center[1], cross_z],
    )

    top_result = top_result.difference(vertical_cross)
    top_result = top_result.difference(horizontal_cross)

    # ---------- Bottom half cuts ----------

    bottom_result = bottom_mesh

    bottom_cavity_z = slice_z - UNIVERSAL_CAVITY_DEPTH / 2

    # Cut one universal square pocket instead of individual pin holes.
    # This removes the switch-body area and leaves room for different PCB/pin variants.
    bottom_cavity = make_box(
        BOTTOM_CAVITY_SIZE,
        BOTTOM_CAVITY_SIZE,
        UNIVERSAL_CAVITY_DEPTH,
        [mesh_center[0], mesh_center[1], bottom_cavity_z],
    )

    bottom_result = bottom_result.difference(bottom_cavity)

    # Add back a support ring/wall around the center post area so the switch is held
    # laterally, then cut a slightly oversized center hole through it.
    center_support_outer_dia = CENTER_HOLE_DIA + CENTER_HOLE_TOLERANCE + 2 * CENTER_SUPPORT_WALL
    center_support = make_cylinder(
        center_support_outer_dia,
        UNIVERSAL_CAVITY_DEPTH,
        [mesh_center[0], mesh_center[1], bottom_cavity_z],
    )

    bottom_result = bottom_result.union(center_support)

    center_hole_z = slice_z - HOLE_DEPTH / 2
    center_hole = make_cylinder(
        CENTER_HOLE_DIA + CENTER_HOLE_TOLERANCE,
        HOLE_DEPTH,
        [mesh_center[0], mesh_center[1], center_hole_z],
    )

    bottom_result = bottom_result.difference(center_hole)

    return top_result, bottom_result


# ---------- Streamlit UI ----------

st.set_page_config(
    page_title="STL to Cherry MX Clicker",
    layout="wide",
)

st.title("STL to Cherry MX Clicker")
st.write(
    "Upload an STL, scale it, choose the slice height visually, then generate top and bottom Cherry MX clicker STLs."
)

with st.sidebar:
    st.header("Controls")
    uploaded_file = st.file_uploader("Upload STL", type=["stl"])

if uploaded_file is None:
    st.info("Upload an STL to begin.")
    st.stop()

try:
    original_mesh = load_mesh_from_upload(uploaded_file)
except Exception as exc:
    st.error(f"Could not load STL: {exc}")
    st.stop()

with st.sidebar:
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

if zmax <= zmin:
    st.error("The uploaded STL has invalid Z bounds.")
    st.stop()

with st.sidebar:
    slice_z = st.slider(
        "Slice Z height",
        min_value=zmin,
        max_value=zmax,
        value=default_slice,
        step=max((zmax - zmin) / 200, 0.001),
    )

    st.divider()
    st.write("Model bounds:")
    st.write(
        f"{bounds[1][0] - bounds[0][0]:.2f} × "
        f"{bounds[1][1] - bounds[0][1]:.2f} × "
        f"{bounds[1][2] - bounds[0][2]:.2f} mm"
    )
    st.write(f"Slice Z: `{slice_z:.3f}`")

top_space = zmax - slice_z
bottom_space = slice_z - zmin

top_needed = max(HOUSING_DEPTH, CROSS_DEPTH)
bottom_needed = max(UNIVERSAL_CAVITY_DEPTH, HOLE_DEPTH)

if top_space < top_needed:
    st.warning("Slice plane may be too high. The top cavity may cut through the model.")

if bottom_space < bottom_needed:
    st.warning("Slice plane may be too low. The bottom universal cavity may cut through the model.")

st.subheader("Input Preview")
st.caption("Gray mesh = uploaded STL. Red plane = slice height. Green wireframe cube = 19 mm Cherry MX reference.")
st.plotly_chart(
    make_input_preview_figure(mesh, slice_z),
    use_container_width=True,
)

if st.button("Generate clicker STLs", type="primary"):
    with st.spinner("Generating top and bottom STLs..."):
        try:
            top_result, bottom_result = generate_clicker_parts(mesh, slice_z)

            st.success("Generated successfully.")

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Top watertight", str(top_result.is_watertight))
            col_b.metric("Bottom watertight", str(bottom_result.is_watertight))
            col_c.metric("Top faces", f"{len(top_result.faces):,}")
            col_d.metric("Bottom faces", f"{len(bottom_result.faces):,}")

            st.subheader("Final Preview")
            st.caption("Top half is lifted upward so you can inspect both parts.")
            st.plotly_chart(
                make_final_preview_figure(top_result, bottom_result),
                use_container_width=True,
            )

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
