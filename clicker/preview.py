import numpy as np
import plotly.graph_objects as go
import trimesh

from clicker.mesh import decimate_for_preview


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
            lighting=dict(
                ambient=0.55,
                diffuse=0.75,
                roughness=0.65,
                specular=0.15,
            ),
            showscale=False,
            hoverinfo="skip",
        )
    )


def add_wire_box(
    fig: go.Figure,
    center,
    size_x: float,
    size_y: float,
    size_z: float,
    name: str,
    color: str,
    width: int = 5,
):
    cx, cy, cz = center
    hx, hy, hz = size_x / 2, size_y / 2, size_z / 2

    p = np.array([
        [cx - hx, cy - hy, cz - hz],
        [cx + hx, cy - hy, cz - hz],
        [cx + hx, cy + hy, cz - hz],
        [cx - hx, cy + hy, cz - hz],
        [cx - hx, cy - hy, cz + hz],
        [cx + hx, cy - hy, cz + hz],
        [cx + hx, cy + hy, cz + hz],
        [cx - hx, cy + hy, cz + hz],
    ])

    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]

    x, y, z = [], [], []
    for a, b in edges:
        x += [p[a, 0], p[b, 0], None]
        y += [p[a, 1], p[b, 1], None]
        z += [p[a, 2], p[b, 2], None]

    fig.add_trace(
        go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode="lines",
            name=name,
            line=dict(color=color, width=width),
            hoverinfo="skip",
        )
    )


def add_cavity_preview_boxes(
    fig: go.Figure,
    mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
):
    center = mesh.bounds.mean(axis=0)
    cavity_x = center[0] + cfg.get("cavity_x_offset", 0.0)
    cavity_y = center[1] + cfg.get("cavity_y_offset", 0.0)

    mode = cfg.get("generation_mode", "split_clicker")

    # ---------- Top cavity preview ----------
    top_cavity_z = slice_z + cfg["housing_depth"] / 2

    add_wire_box(
        fig,
        center=[cavity_x, cavity_y, top_cavity_z],
        size_x=cfg["housing_size"],
        size_y=cfg["housing_size"],
        size_z=cfg["housing_depth"],
        name="Top cavity preview",
        color="#EF4444",
        width=5,
    )

    # ---------- Bottom cavity preview ----------
    # Hide this preview in Top Shell + Base mode since the
    # base no longer contains a simple bottom cavity.
    if mode != "top_shell_base":
        bottom_cavity_z = slice_z - cfg["bottom_cavity_depth"] / 2

        add_wire_box(
            fig,
            center=[cavity_x, cavity_y, bottom_cavity_z],
            size_x=cfg["bottom_cavity_size"],
            size_y=cfg["bottom_cavity_size"],
            size_z=cfg["bottom_cavity_depth"],
            name="Bottom cavity preview",
            color="#3B82F6",
            width=5,
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


def make_preview_figure(
    mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
    generated=False,
    top_mesh=None,
    bottom_mesh=None,
):
    fig = go.Figure()

    if generated and top_mesh is not None and bottom_mesh is not None:
        top_preview = top_mesh.copy()
        bottom_preview = bottom_mesh.copy()

        gap = max(mesh.extents[0], mesh.extents[1], 20.0) * 0.80

        top_preview.apply_translation([0, -gap / 2, 0])
        bottom_preview.apply_translation([0, gap / 2, 0])

        add_mesh(fig, top_preview, "Top half", 0.86)
        fig.data[-1].color = "#EF4444"

        add_mesh(fig, bottom_preview, "Bottom half", 0.86)
        fig.data[-1].color = "#3B82F6"

    else:
        add_mesh(fig, mesh, "Uploaded STL", 0.50)
        add_slice_plane(fig, mesh, slice_z)
        add_cavity_preview_boxes(fig, mesh, slice_z, cfg)

    fig.update_layout(
        height=735,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        scene=dict(
            aspectmode="data",
            bgcolor="white",
            xaxis=dict(
                visible=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
            ),
            yaxis=dict(
                visible=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
            ),
            zaxis=dict(
                visible=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
            ),
            camera=dict(
                projection=dict(type="orthographic"),
                eye=dict(
                    x=1.45,
                    y=-1.55,
                    z=1.05,
                ),
            ),
        ),
    )

    return fig
