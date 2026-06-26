import streamlit as st

from clicker.config import APP_VERSION, DEFAULTS


def initialize_session_state():
    for key, value in {
        "generated": False,
        "top_mesh": None,
        "bottom_mesh": None,
        "last_signature": None,
        "export_name": "clicker",
    }.items():
        st.session_state.setdefault(key, value)


def render_sidebar_header():
    with st.sidebar:
        st.markdown("### Controls")
        st.caption(f"Version: {APP_VERSION}")
        uploaded_file = st.file_uploader("Upload STL", type=["stl"])
        st.divider()
    return uploaded_file


def reset_generation_for_new_file(uploaded_file):
    file_signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state.last_signature != file_signature:
        st.session_state.generated = False
        st.session_state.top_mesh = None
        st.session_state.bottom_mesh = None
        st.session_state.last_signature = file_signature


def render_scale_slider() -> float:
    return st.slider(
        "Scale",
        min_value=0.10,
        max_value=5.00,
        value=1.00,
        step=0.01,
        label_visibility="collapsed",
    )


def render_geometry_controls(mesh, zmin: float, zmax: float, default_slice: float) -> tuple[float, dict, bool]:
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

        render_clearance_warnings(mesh, zmin, zmax, slice_z, cfg)

        st.write("")
        st.write("")

        generate_clicked = st.button(
            "Generate",
            type="primary",
            use_container_width=True,
        )

        return slice_z, cfg, generate_clicked


def render_clearance_warnings(mesh, zmin: float, zmax: float, slice_z: float, cfg: dict):
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

    center = mesh.bounds.mean(axis=0)

    cavity_x = center[0] + cfg["cavity_x_offset"]
    cavity_y = center[1] + cfg["cavity_y_offset"]

    xmin, ymin, _ = mesh.bounds[0]
    xmax, ymax, _ = mesh.bounds[1]

    largest_cavity = max(
        cfg["housing_size"],
        cfg["bottom_cavity_size"],
    )

    half = largest_cavity / 2

    x_left = cavity_x - half - xmin
    x_right = xmax - (cavity_x + half)

    y_back = cavity_y - half - ymin
    y_front = ymax - (cavity_y + half)

    if x_left < 0:
        st.warning(
            f"⚠️ Cavity extends {-x_left:.2f} mm past the left side."
        )

    if x_right < 0:
        st.warning(
            f"⚠️ Cavity extends {-x_right:.2f} mm past the right side."
        )

    if y_back < 0:
        st.warning(
            f"⚠️ Cavity extends {-y_back:.2f} mm past the back side."
        )

    if y_front < 0:
        st.warning(
            f"⚠️ Cavity extends {-y_front:.2f} mm past the front side."
        )
