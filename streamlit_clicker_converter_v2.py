import io
import re
import tempfile
import zipfile

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import trimesh


# ============================================================
# STL to Cherry MX Clicker Converter - Streamlit v2
# ============================================================
# GitHub/Streamlit notes:
# requirements.txt should include:
# streamlit
# trimesh
# numpy
# plotly
# manifold3d
# scipy
# ============================================================

APP_VERSION = "v2-cad-layout-2026-06-25"


# -----------------------------
# Default geometry configuration
# -----------------------------
DEFAULTS = {
    # Top half / switch stem side
    "housing_size": 16.0,
    "housing_depth": 5.2,
    "cross_width": 4.20,
    "cross_arm": 1.45,
    "cross_depth": 4.2,
    "stem_tolerance": 0.20,
    "top_circular_clearance": 1.00,  # diameter is cross width + tolerance + this value

    # Bottom half / switch body side
    "bottom_cavity_size": 16.0,
    "bottom_cavity_depth": 5.2,
    "center_hole_dia": 4.00,
    "center_hole_tolerance": 0.30,
    "center_support_outer_dia": 7.00,
    "extra_hole_depth": 5.0,
}


# -----------------------------
# Page setup / CSS
# -----------------------------
st.set_page_config(
    page_title="STL to Cherry MX Clicker",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        header[data-testid="stHeader"] {height: 0rem; visibility: hidden;}
        div[data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
        div[data-testid="stDecoration"] {visibility: hidden; height: 0%;}
        footer {visibility: hidden;}
        .block-container {
            padding-top: 0.35rem !important;
            padding-bottom: 0.25rem !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            max-width: 100% !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        div[data-testid="stVerticalBlock"] {gap: 0.35rem !important;}
        .stPlotlyChart {margin-top: -0.25rem !important;}
        h1, h2, h3, p {margin-top: 0rem !important; margin-bottom: 0.2rem !important;}
        .small-note {font-size: 0.78rem; color: #6b7280;}
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Session state
# -----------------------------
for key, value in {
    "generated": False,
    "top_mesh": None,
    "bottom_mesh": None,
    "last_signature": None,
}.items():
    st.session_state.setdefault(key, value)


# -----------------------------
# Mesh helpers
# -----------------------------
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


def make_box(x: float, y: float, z: float, center) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=[x, y, z])
    mesh.apply_translation(center)
    return mesh


def make_cylinder(diameter: float, height: float, center, sections: int = 72) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(
        radius=diameter / 2,
        height=height,
        sections=sections,
    )
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
    """Boolean wrapper with a clearer error if Streamlit lacks a boolean backend."""
    try:
        result = base.difference(cutter)
    except Exception as exc:
        raise RuntimeError(
            f"Boolean cut failed while cutting {label}. Add manifold3d to requirements.txt "
            f"or try a simpler/watertight STL. Original error: {exc}"
        ) from exc

    if result is None or result.is_empty:
        raise RuntimeError(f"Boolean cut produced an empty mesh while cutting {label}.")
    return result


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


# -----------------------------
# Clicker geometry
# -----------------------------
def generate_clicker_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict):
    center = mesh.bounds.mean(axis=0)

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

    # ---------- TOP HALF ----------
    # Goal: cut a 16 mm switch-housing pocket while leaving a circular center boss
    # around the MX stem cross. This replaces the old square boss.
    top_result = top_mesh

    housing_size = cfg["housing_size"]
    housing_depth = cfg["housing_depth"]
    cross_width = cfg["cross_width"] + cfg["stem_tolerance"]
    cross_arm = cfg["cross_arm"] + cfg["stem_tolerance"]
    cross_depth = cfg["cross_depth"]

    top_cut_z = slice_z + housing_depth / 2

    top_cavity_box = make_box(
        housing_size,
        housing_size,
        housing_depth,
        [center[0], center[1], top_cut_z],
    )

    circular_boss_dia = max(cross_width, cross_arm) + cfg["top_circular_clearance"]
    circular_keepout = make_cylinder(
        circular_boss_dia,
        housing_depth + 0.20,
        [center[0], center[1], top_cut_z],
    )

    # This cutter is the square pocket minus the circular boss area.
    # Subtracting this from the model leaves a round boss in the middle.
    top_pocket_cutter = safe_boolean_difference(
        top_cavity_box,
        circular_keepout,
        "top circular boss cutter",
    )
    top_result = safe_boolean_difference(top_result, top_pocket_cutter, "top switch housing pocket")

    cross_z = slice_z + cross_depth / 2
    vertical_cross = make_box(
        cross_arm,
        cross_width,
        cross_depth,
        [center[0], center[1], cross_z],
    )
    horizontal_cross = make_box(
        cross_width,
        cross_arm,
        cross_depth,
        [center[0], center[1], cross_z],
    )

    top_result = safe_boolean_difference(top_result, vertical_cross, "vertical MX stem cross")
    top_result = safe_boolean_difference(top_result, horizontal_cross, "horizontal MX stem cross")

    # ---------- BOTTOM HALF ----------
    # Goal: universal bottom cavity. Remove the switch-body pocket while keeping
    # a center cylindrical support, then cut the center hole through that support.
    bottom_result = bottom_mesh

    bottom_cavity_depth = cfg["bottom_cavity_depth"]
    bottom_cavity_size = cfg["bottom_cavity_size"]
    hole_depth = bottom_cavity_depth + cfg["extra_hole_depth"]

    bottom_cavity_z = slice_z - bottom_cavity_depth / 2
    bottom_cavity_box = make_box(
        bottom_cavity_size,
        bottom_cavity_size,
        bottom_cavity_depth,
        [center[0], center[1], bottom_cavity_z],
    )

    center_support = make_cylinder(
        cfg["center_support_outer_dia"],
        bottom_cavity_depth + 0.20,
        [center[0], center[1], bottom_cavity_z],
    )

    bottom_pocket_cutter = safe_boolean_difference(
        bottom_cavity_box,
        center_support,
        "bottom universal cavity cutter",
    )
    bottom_result = safe_boolean_difference(bottom_result, bottom_pocket_cutter, "bottom universal cavity")

    center_hole_dia = cfg["center_hole_dia"] + cfg["center_hole_tolerance"]
    center_hole_z = slice_z - hole_depth / 2
    center_hole = make_cylinder(
        center_hole_dia,
        hole_depth,
        [center[0], center[1], center_hole_z],
    )
    bottom_result = safe_boolean_difference(bottom_result, center_hole, "bottom center hole")

    return top_result, bottom_result


# -----------------------------
# Plotly visualization helpers
# -----------------------------
def decimate_for_preview(mesh: trimesh.Trimesh, max_faces: int = 14000) -> trimesh.Trimesh:
    if len(mesh.faces) <= max_faces:
        return mesh
    face_indices = np.linspace(0, len(mesh.faces) - 1, max_faces).astype(int)
    return mesh.submesh([face_indices], append=True, repair=False)


def add_mesh(fig: go.Figure, mesh: trimesh.Trimesh, name: str, opacity: float):
    preview = decimate_for_preview(mesh)
    v = preview.vertices
    f = preview.faces
    fig.add_trace(
        go.Mesh3d(
            x=v[:, 0],
            y=v[:, 1],
            z=v[:, 2],
            i=f[:, 0],
            j=f[:, 1],
            k=f[:, 2],
            name=name,
            opacity=opacity,
            color="#D8DCE2" if name == "Uploaded STL" else None,
            flatshading=True,
            lighting=dict(ambient=0.55, diffuse=0.75, roughness=0.65, specular=0.15),
            showscale=False,
            hoverinfo="skip",
        )
    )


def add_reference_cube(fig: go.Figure, center_xy, z_center: float, size: float = 19.0):
    cx, cy = center_xy
    h = size / 2
    p = np.array([
        [cx - h, cy - h, z_center - h], [cx + h, cy - h, z_center - h],
        [cx + h, cy + h, z_center - h], [cx - h, cy + h, z_center - h],
        [cx - h, cy - h, z_center + h], [cx + h, cy - h, z_center + h],
        [cx + h, cy + h, z_center + h], [cx - h, cy + h, z_center + h],
    ])
    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    x, y, z = [], [], []
    for a, b in edges:
        x += [p[a,0], p[b,0], None]
        y += [p[a,1], p[b,1], None]
        z += [p[a,2], p[b,2], None]
    fig.add_trace(
        go.Scatter3d(
            x=x, y=y, z=z,
            mode="lines",
            name="19 mm MX reference",
            line=dict(color="#22C55E", width=5),
            hoverinfo="skip",
        )
    )


def add_slice_plane(fig: go.Figure, mesh: trimesh.Trimesh, slice_z: float):
    bounds = mesh.bounds
    xmin, ymin, _ = bounds[0]
    xmax, ymax, _ = bounds[1]
    cx, cy = mesh.bounds.mean(axis=0)[:2]
    size = max(xmax - xmin, ymax - ymin, 19.0) * 1.20
    x = np.array([cx - size / 2, cx + size / 2])
    y = np.array([cy - size / 2, cy + size / 2])
    xx, yy = np.meshgrid(x, y)
    zz = np.full_like(xx, slice_z)
    fig.add_trace(
        go.Surface(
            x=xx,
            y=yy,
            z=zz,
            name="Slice plane",
            opacity=0.28,
            colorscale=[[0, "#EF4444"], [1, "#EF4444"]],
            showscale=False,
            hoverinfo="skip",
        )
    )


def make_preview_figure(mesh: trimesh.Trimesh, slice_z: float, generated=False, top_mesh=None, bottom_mesh=None):
    fig = go.Figure()

    if generated and top_mesh is not None and bottom_mesh is not None:
        top_preview = top_mesh.copy()
        bottom_preview = bottom_mesh.copy()
        # Side-by-side split, not vertical stacking.
        gap = max(mesh.extents[0], mesh.extents[1], 20.0) * 0.65
        top_preview.apply_translation([-gap / 2, 0, 0])
        bottom_preview.apply_translation([gap / 2, 0, 0])

        add_mesh(fig, top_preview, "Top half", 0.86)
        fig.data[-1].color = "#EF4444"
        add_mesh(fig, bottom_preview, "Bottom half", 0.86)
        fig.data[-1].color = "#3B82F6"
    else:
        add_mesh(fig, mesh, "Uploaded STL", 0.50)
        add_slice_plane(fig, mesh, slice_z)
        center = mesh.bounds.mean(axis=0)
        add_reference_cube(fig, (center[0], center[1]), slice_z, size=19.0)

    fig.update_layout(
        height=735,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        scene=dict(
            aspectmode="data",
            bgcolor="white",
            xaxis=dict(visible=False, showbackground=False, showgrid=False, zeroline=False),
            yaxis=dict(visible=False, showbackground=False, showgrid=False, zeroline=False),
            zaxis=dict(visible=False, showbackground=False, showgrid=False, zeroline=False),
            camera=dict(
                projection=dict(type="orthographic"),
                eye=dict(x=1.45, y=-1.55, z=1.05),
            ),
        ),
    )
    return fig


# -----------------------------
# Sidebar controls
# -----------------------------
with st.sidebar:
    st.markdown("### Controls")
    st.caption(f"Version: {APP_VERSION}")

    uploaded_file = st.file_uploader("Upload STL", type=["stl"])

    output_name = clean_filename(
        st.text_input("Output filename", value="clicker", help="Downloads will use name_top.stl and name_bottom.stl")
    )

    st.divider()


if uploaded_file is None:
    st.info("Upload an STL to begin.")
    st.stop()

try:
    original_mesh = load_mesh_from_upload(uploaded_file)
except Exception as exc:
    st.error(f"Could not load STL: {exc}")
    st.stop()

# Reset generation if file identity changes.
file_signature = (uploaded_file.name, uploaded_file.size)
if st.session_state.last_signature != file_signature:
    st.session_state.generated = False
    st.session_state.top_mesh = None
    st.session_state.bottom_mesh = None
    st.session_state.last_signature = file_signature


# -----------------------------
# Main control: scale near viewer
# -----------------------------
scale = st.slider(
    "Scale",
    min_value=0.10,
    max_value=5.00,
    value=1.00,
    step=0.01,
    label_visibility="collapsed",
)

mesh = apply_scale_about_center(original_mesh, scale)
bounds = mesh.bounds
zmin, zmax = float(bounds[0][2]), float(bounds[1][2])
if zmax <= zmin:
    st.error("The uploaded STL has invalid Z bounds.")
    st.stop()

default_slice = float((zmin + zmax) / 2)


# Sidebar controls that depend on mesh bounds.
with st.sidebar:
    slice_z = st.slider(
        "Slice Z height",
        min_value=zmin,
        max_value=zmax,
        value=default_slice,
        step=max((zmax - zmin) / 250, 0.001),
    )

    with st.expander("Advanced settings", expanded=False):
        st.markdown("**Fit**")
        stem_tolerance = st.number_input("Stem tolerance (mm)", 0.00, 1.00, DEFAULTS["stem_tolerance"], 0.05)
        center_hole_tolerance = st.number_input("Center hole tolerance (mm)", 0.00, 1.50, DEFAULTS["center_hole_tolerance"], 0.05)
        top_circular_clearance = st.number_input("Top circular clearance (mm)", 0.00, 3.00, DEFAULTS["top_circular_clearance"], 0.10)

        st.markdown("**Dimensions**")
        housing_size = st.number_input("Top housing pocket size (mm)", 10.0, 25.0, DEFAULTS["housing_size"], 0.1)
        housing_depth = st.number_input("Top housing depth (mm)", 1.0, 12.0, DEFAULTS["housing_depth"], 0.1)
        cross_width = st.number_input("Cross width (mm)", 2.0, 8.0, DEFAULTS["cross_width"], 0.05)
        cross_arm = st.number_input("Cross arm thickness (mm)", 0.5, 4.0, DEFAULTS["cross_arm"], 0.05)
        cross_depth = st.number_input("Cross depth (mm)", 1.0, 10.0, DEFAULTS["cross_depth"], 0.1)
        bottom_cavity_size = st.number_input("Bottom cavity size (mm)", 10.0, 25.0, DEFAULTS["bottom_cavity_size"], 0.1)
        bottom_cavity_depth = st.number_input("Bottom cavity depth (mm)", 1.0, 12.0, DEFAULTS["bottom_cavity_depth"], 0.1)
        center_hole_dia = st.number_input("Center hole diameter (mm)", 2.0, 8.0, DEFAULTS["center_hole_dia"], 0.05)
        center_support_outer_dia = st.number_input("Center support outer diameter (mm)", 4.0, 12.0, DEFAULTS["center_support_outer_dia"], 0.1)
        extra_hole_depth = st.number_input("Extra center hole depth (mm)", 0.0, 15.0, DEFAULTS["extra_hole_depth"], 0.5)

    cfg = {
        "housing_size": housing_size,
        "housing_depth": housing_depth,
        "cross_width": cross_width,
        "cross_arm": cross_arm,
        "cross_depth": cross_depth,
        "stem_tolerance": stem_tolerance,
        "top_circular_clearance": top_circular_clearance,
        "bottom_cavity_size": bottom_cavity_size,
        "bottom_cavity_depth": bottom_cavity_depth,
        "center_hole_dia": center_hole_dia,
        "center_hole_tolerance": center_hole_tolerance,
        "center_support_outer_dia": center_support_outer_dia,
        "extra_hole_depth": extra_hole_depth,
    }

    top_space = zmax - slice_z
    bottom_space = slice_z - zmin
    top_needed = max(cfg["housing_depth"], cfg["cross_depth"])
    bottom_needed = cfg["bottom_cavity_depth"] + cfg["extra_hole_depth"]

    if top_space < top_needed:
        st.warning("Slice may be too high for the top cavity.")
    if bottom_space < bottom_needed:
        st.warning("Slice may be too low for the bottom cavity.")

    st.caption(
        f"Bounds: {mesh.extents[0]:.2f} × {mesh.extents[1]:.2f} × {mesh.extents[2]:.2f} mm"
    )
    st.caption(f"Slice Z: {slice_z:.3f}")

    generate_clicked = st.button("Generate", type="primary", use_container_width=True)

    if generate_clicked:
        with st.spinner("Generating STLs..."):
            try:
                top_result, bottom_result = generate_clicker_parts(mesh, slice_z, cfg)
                st.session_state.top_mesh = top_result
                st.session_state.bottom_mesh = bottom_result
                st.session_state.generated = True
                st.success("Generated")
            except Exception as exc:
                st.session_state.generated = False
                st.session_state.top_mesh = None
                st.session_state.bottom_mesh = None
                st.error(f"Generation failed: {exc}")

    if st.session_state.generated and st.session_state.top_mesh is not None and st.session_state.bottom_mesh is not None:
        top_bytes = export_stl_bytes(st.session_state.top_mesh)
        bottom_bytes = export_stl_bytes(st.session_state.bottom_mesh)
        zip_bytes = make_zip_bytes(st.session_state.top_mesh, st.session_state.bottom_mesh, output_name)

        st.divider()
        st.markdown("**Downloads**")
        st.download_button(
            "Download ZIP",
            data=zip_bytes,
            file_name=f"{output_name}_clicker_parts.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.download_button(
            "Download top STL",
            data=top_bytes,
            file_name=f"{output_name}_top.stl",
            mime="model/stl",
            use_container_width=True,
        )
        st.download_button(
            "Download bottom STL",
            data=bottom_bytes,
            file_name=f"{output_name}_bottom.stl",
            mime="model/stl",
            use_container_width=True,
        )

        if st.button("Reset preview", use_container_width=True):
            st.session_state.generated = False
            st.session_state.top_mesh = None
            st.session_state.bottom_mesh = None
            st.rerun()


# -----------------------------
# Single viewer
# -----------------------------
fig = make_preview_figure(
    mesh,
    slice_z,
    generated=st.session_state.generated,
    top_mesh=st.session_state.top_mesh,
    bottom_mesh=st.session_state.bottom_mesh,
)
st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

# Tiny status row below viewer. Kept compact to avoid page scroll.
if st.session_state.generated and st.session_state.top_mesh is not None and st.session_state.bottom_mesh is not None:
    st.caption(
        f"Generated: top watertight={st.session_state.top_mesh.is_watertight}, "
        f"bottom watertight={st.session_state.bottom_mesh.is_watertight}"
    )
else:
    st.caption("Preview: gray STL, red slice plane, green 19 mm Cherry MX reference cube.")
