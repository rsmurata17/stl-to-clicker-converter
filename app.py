import streamlit as st

from clicker.config import DEFAULTS
from clicker.export import clean_filename, export_stl_bytes, make_zip_bytes
from clicker.geometry import generate_clicker_parts
from clicker.mesh import apply_scale_about_center, load_mesh_from_upload
from clicker.preview import make_preview_figure
from clicker.styles import APP_CSS
from clicker.ui import (
    initialize_session_state,
    render_geometry_controls,
    render_scale_slider,
    render_sidebar_header,
    reset_generation_for_new_file,
)


st.set_page_config(
    page_title="STL to Cherry MX Clicker",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)

initialize_session_state()
uploaded_file = render_sidebar_header()

if uploaded_file is None:
    st.info("Upload an STL to begin.")
    st.stop()

try:
    original_mesh = load_mesh_from_upload(uploaded_file)
except Exception as exc:
    st.error(f"Could not load STL: {exc}")
    st.stop()

reset_generation_for_new_file(uploaded_file)

scale = render_scale_slider()
mesh = apply_scale_about_center(original_mesh, scale)

bounds = mesh.bounds
zmin, zmax = float(bounds[0][2]), float(bounds[1][2])
if zmax <= zmin:
    st.error("The uploaded STL has invalid Z bounds.")
    st.stop()

default_slice = float((zmin + zmax) / 2)
slice_z, cfg, generate_clicked = render_geometry_controls(mesh, zmin, zmax, default_slice)

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

with st.sidebar:
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
            st.session_state.generated = False
            st.session_state.top_mesh = None
            st.session_state.bottom_mesh = None
            st.rerun()

fig = make_preview_figure(
    mesh,
    slice_z,
    cfg,
    generated=st.session_state.generated,
    top_mesh=st.session_state.top_mesh,
    bottom_mesh=st.session_state.bottom_mesh,
)
st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
