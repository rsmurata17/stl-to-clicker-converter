import streamlit as st

from clicker.config import APP_VERSION, DEFAULTS
from clicker.export import clean_filename, export_stl_bytes, make_zip_bytes
from clicker.geometry import generate_clicker_parts
from clicker.mesh_utils import apply_scale_about_center, load_mesh_from_upload
from clicker.preview import make_preview_figure
from clicker.ui import configure_page, inject_css, initialize_session_state, reset_generated_meshes


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


configure_page()
inject_css()
initialize_session_state()


# -----------------------------
# Sidebar controls
# -----------------------------
with st.sidebar:
    st.markdown("### Controls")
    st.caption(f"Version: {APP_VERSION}")

    uploaded_file = st.file_uploader("Upload STL", type=["stl"])

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
    reset_generated_meshes()
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

    x_range = max(float(mesh.extents[0]) / 2, 10.0)
    cavity_x_offset = st.slider(
        "Cavity X offset",
        min_value=-x_range,
        max_value=x_range,
        value=DEFAULTS["cavity_x_offset"],
        step=0.1,
        help="Moves the top and bottom cavity cuts left/right on the X axis.",
    )

    y_range = max(float(mesh.extents[1]) / 2, 10.0)
    cavity_y_offset = st.slider(
        "Cavity Y offset",
        min_value=-y_range,
        max_value=y_range,
        value=DEFAULTS["cavity_y_offset"],
        step=0.1,
        help="Moves the top and bottom cavity cuts forward/backward on the Y axis.",
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

    cfg = {
        "housing_size": housing_size,
        "housing_depth": housing_depth,
        "cross_width": cross_width,
        "cross_arm": cross_arm,
        "cross_depth": cross_depth,
        "stem_tolerance": stem_tolerance,
        "top_circular_clearance": top_circular_clearance,
        "cavity_x_offset": cavity_x_offset,
        "cavity_y_offset": cavity_y_offset,
        "bottom_cavity_size": bottom_cavity_size,
        "bottom_cavity_depth": bottom_cavity_depth,
        "center_hole_dia": center_hole_dia,
        "center_hole_tolerance": center_hole_tolerance,
        "center_support_outer_dia": center_support_outer_dia,
    }

    top_space = zmax - slice_z
    bottom_space = slice_z - zmin

    top_needed = max(
        cfg["housing_depth"],
        cfg["cross_depth"],
    )
    bottom_needed = cfg["bottom_cavity_depth"]

    st.caption(f"Top clearance: {top_space:.2f} / {top_needed:.2f} mm")
    st.caption(f"Bottom clearance: {bottom_space:.2f} / {bottom_needed:.2f} mm")

    if top_space < top_needed:
        st.warning(
            f"⚠️ Slice is {top_needed - top_space:.2f} mm too high. "
            "The top cavity may be clipped."
        )

    if bottom_space < bottom_needed:
        st.warning(
            f"⚠️ Slice is {bottom_needed - bottom_space:.2f} mm too low. "
            "The bottom cavity may be clipped."
        )

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
                reset_generated_meshes()
                st.error(f"Generation failed: {exc}")

    if st.session_state.generated and st.session_state.top_mesh is not None and st.session_state.bottom_mesh is not None:
        st.divider()
        st.markdown("**Downloads**")
        export_name_raw = st.text_input(
            "Export filename",
            value=st.session_state.export_name,
            help="Files will export as name_top.stl and name_bottom.stl.",
            key="export_name_input",
        )

        export_name = clean_filename(export_name_raw)
        st.session_state.export_name = export_name

        top_bytes = export_stl_bytes(st.session_state.top_mesh)
        bottom_bytes = export_stl_bytes(st.session_state.bottom_mesh)
        zip_bytes = make_zip_bytes(
            st.session_state.top_mesh,
            st.session_state.bottom_mesh,
            export_name,
        )

        st.download_button(
            "Download ZIP",
            data=zip_bytes,
            file_name=f"{export_name}_clicker_parts.zip",
            mime="application/zip",
            use_container_width=True,
        )
        st.download_button(
            "Download top STL",
            data=top_bytes,
            file_name=f"{export_name}_top.stl",
            mime="model/stl",
            use_container_width=True,
        )
        st.download_button(
            "Download bottom STL",
            data=bottom_bytes,
            file_name=f"{export_name}_bottom.stl",
            mime="model/stl",
            use_container_width=True,
        )

        if st.button("Reset preview", use_container_width=True):
            reset_generated_meshes()
            st.rerun()


# -----------------------------
# Single viewer
# -----------------------------
fig = make_preview_figure(
    mesh,
    slice_z,
    cfg,
    generated=st.session_state.generated,
    top_mesh=st.session_state.top_mesh,
    bottom_mesh=st.session_state.bottom_mesh,
)
st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

# No extra text below the viewer; this keeps the app from scrolling on typical displays.
