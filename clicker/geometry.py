import trimesh

from clicker.mesh import make_box, make_cylinder, safe_boolean_difference


def split_mesh(mesh: trimesh.Trimesh, slice_z: float) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
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

    return top_mesh, bottom_mesh


def cut_top_cavity(top_mesh: trimesh.Trimesh, slice_z: float, cavity_x: float, cavity_y: float, cfg: dict) -> trimesh.Trimesh:
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
        [cavity_x, cavity_y, top_cut_z],
    )

    circular_boss_dia = max(cross_width, cross_arm) + cfg["top_circular_clearance"]
    circular_keepout = make_cylinder(
        circular_boss_dia,
        housing_depth + 0.20,
        [cavity_x, cavity_y, top_cut_z],
    )

    top_pocket_cutter = safe_boolean_difference(
        top_cavity_box,
        circular_keepout,
        "top circular boss cutter",
    )
    result = safe_boolean_difference(top_mesh, top_pocket_cutter, "top switch housing pocket")

    cross_z = slice_z + cross_depth / 2
    vertical_cross = make_box(
        cross_arm,
        cross_width,
        cross_depth,
        [cavity_x, cavity_y, cross_z],
    )
    horizontal_cross = make_box(
        cross_width,
        cross_arm,
        cross_depth,
        [cavity_x, cavity_y, cross_z],
    )

    result = safe_boolean_difference(result, vertical_cross, "vertical MX stem cross")
    result = safe_boolean_difference(result, horizontal_cross, "horizontal MX stem cross")
    return result


def cut_bottom_cavity(bottom_mesh: trimesh.Trimesh, slice_z: float, cavity_x: float, cavity_y: float, cfg: dict) -> trimesh.Trimesh:
    bottom_cavity_depth = cfg["bottom_cavity_depth"]
    bottom_cavity_size = cfg["bottom_cavity_size"]

    bottom_cavity_z = slice_z - bottom_cavity_depth / 2
    bottom_cavity_box = make_box(
        bottom_cavity_size,
        bottom_cavity_size,
        bottom_cavity_depth,
        [cavity_x, cavity_y, bottom_cavity_z],
    )

    # Center support is half the total cavity height and starts at the bottom of the pocket.
    center_support_height = bottom_cavity_depth / 2
    center_support_z = slice_z - bottom_cavity_depth + center_support_height / 2

    center_support = make_cylinder(
        cfg["center_support_outer_dia"],
        center_support_height,
        [cavity_x, cavity_y, center_support_z],
    )

    bottom_pocket_cutter = safe_boolean_difference(
        bottom_cavity_box,
        center_support,
        "bottom universal cavity cutter",
    )
    result = safe_boolean_difference(bottom_mesh, bottom_pocket_cutter, "bottom universal cavity")

    center_hole_dia = cfg["center_hole_dia"] + cfg["center_hole_tolerance"]
    center_hole_depth = bottom_cavity_depth
    center_hole_z = slice_z - center_hole_depth / 2
    center_hole = make_cylinder(
        center_hole_dia,
        center_hole_depth,
        [cavity_x, cavity_y, center_hole_z],
    )
    result = safe_boolean_difference(result, center_hole, "bottom center pin hole")
    return result


def generate_clicker_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    center = mesh.bounds.mean(axis=0)
    cavity_x = center[0] + cfg.get("cavity_x_offset", 0.0)
    cavity_y = center[1] + cfg.get("cavity_y_offset", 0.0)

    top_mesh, bottom_mesh = split_mesh(mesh, slice_z)
    top_result = cut_top_cavity(top_mesh, slice_z, cavity_x, cavity_y, cfg)
    bottom_result = cut_bottom_cavity(bottom_mesh, slice_z, cavity_x, cavity_y, cfg)
    return top_result, bottom_result
