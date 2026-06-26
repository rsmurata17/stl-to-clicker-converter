import trimesh
from shapely.geometry import LineString, MultiPolygon
from shapely.ops import polygonize, unary_union

from clicker.mesh import make_box, make_cylinder, safe_boolean_difference


def generate_clicker_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict):
    mode = cfg.get("generation_mode", "split_clicker")

    if mode == "top_shell_base":
        return generate_top_shell_base_parts(mesh, slice_z, cfg)

    return generate_split_clicker_parts(mesh, slice_z, cfg)


def generate_split_clicker_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict):
    top_mesh, bottom_mesh = slice_top_and_bottom(mesh, slice_z)

    top_result = cut_top_switch_cavity(top_mesh, mesh, slice_z, cfg)
    bottom_result = cut_bottom_switch_cavity(bottom_mesh, mesh, slice_z, cfg)

    return top_result, bottom_result


def generate_top_shell_base_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict):
    top_mesh = mesh.slice_plane(
        plane_origin=[0, 0, slice_z],
        plane_normal=[0, 0, 1],
        cap=True,
    )

    if top_mesh is None or top_mesh.is_empty:
        raise ValueError("Top slice failed. Move the slice plane lower.")

    top_result = cut_top_switch_cavity(top_mesh, mesh, slice_z, cfg)
    shell_base = create_top_shell_base(top_mesh, mesh, slice_z, cfg)

    shell_base = cut_bottom_switch_cavity(shell_base, mesh, slice_z, cfg)

    return top_result, shell_base


def slice_top_and_bottom(mesh: trimesh.Trimesh, slice_z: float):
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


def get_cavity_center(reference_mesh: trimesh.Trimesh, cfg: dict):
    center = reference_mesh.bounds.mean(axis=0)
    cavity_x = center[0] + cfg.get("cavity_x_offset", 0.0)
    cavity_y = center[1] + cfg.get("cavity_y_offset", 0.0)
    return cavity_x, cavity_y


def cut_top_switch_cavity(
    top_mesh: trimesh.Trimesh,
    reference_mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
):
    cavity_x, cavity_y = get_cavity_center(reference_mesh, cfg)

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

    top_result = safe_boolean_difference(
        top_result,
        top_pocket_cutter,
        "top switch housing pocket",
    )

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

    top_result = safe_boolean_difference(
        top_result,
        vertical_cross,
        "vertical MX stem cross",
    )

    top_result = safe_boolean_difference(
        top_result,
        horizontal_cross,
        "horizontal MX stem cross",
    )

    return top_result


def cut_bottom_switch_cavity(
    bottom_mesh: trimesh.Trimesh,
    reference_mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
):
    cavity_x, cavity_y = get_cavity_center(reference_mesh, cfg)

    bottom_result = bottom_mesh

    bottom_cavity_depth = cfg["bottom_cavity_depth"]
    bottom_cavity_size = cfg["bottom_cavity_size"]

    bottom_cavity_z = slice_z - bottom_cavity_depth / 2

    bottom_cavity_box = make_box(
        bottom_cavity_size,
        bottom_cavity_size,
        bottom_cavity_depth,
        [cavity_x, cavity_y, bottom_cavity_z],
    )

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

    bottom_result = safe_boolean_difference(
        bottom_result,
        bottom_pocket_cutter,
        "bottom universal cavity",
    )

    center_hole_dia = cfg["center_hole_dia"] + cfg["center_hole_tolerance"]
    center_hole_depth = bottom_cavity_depth
    center_hole_z = slice_z - center_hole_depth / 2

    center_hole = make_cylinder(
        center_hole_dia,
        center_hole_depth,
        [cavity_x, cavity_y, center_hole_z],
    )

    bottom_result = safe_boolean_difference(
        bottom_result,
        center_hole,
        "bottom center pin hole",
    )

    return bottom_result


def create_top_shell_base(
    top_mesh: trimesh.Trimesh,
    reference_mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
):
    wall_height = cfg["shell_wall_height"]
    wall_thickness = cfg["shell_wall_thickness"]
    outline_padding = cfg["shell_outline_padding"]
    base_floor = cfg["shell_base_floor"]

    total_depth = wall_height + cfg["bottom_cavity_depth"] + base_floor

    section = reference_mesh.section(
        plane_origin=[0, 0, slice_z],
        plane_normal=[0, 0, 1],
    )

    if section is None:
        raise ValueError("Could not create outline from slice plane.")

    lines = []

    for path in section.discrete:
        if len(path) >= 2:
            points_2d = [(float(p[0]), float(p[1])) for p in path]
            lines.append(LineString(points_2d))

    if not lines:
        raise ValueError("Slice outline failed. Try moving the slice plane.")

    polygons = list(polygonize(lines))

    if not polygons:
        raise ValueError("Could not turn slice outline into a closed polygon.")

    outline = unary_union(polygons)

    if isinstance(outline, MultiPolygon):
        outline = max(outline.geoms, key=lambda polygon: polygon.area)

    inner_outline = outline.buffer(
        outline_padding,
        join_style=2,
    )

    outer_outline = outline.buffer(
        outline_padding + wall_thickness,
        join_style=2,
    )

    outer_base = trimesh.creation.extrude_polygon(
        outer_outline,
        height=total_depth,
    )

    outer_base.apply_translation([0, 0, slice_z - total_depth])

    inner_socket_cut = trimesh.creation.extrude_polygon(
        inner_outline,
        height=wall_height + 0.05,
    )

    inner_socket_cut.apply_translation([0, 0, slice_z - wall_height - 0.025])

    shell_base = safe_boolean_difference(
        outer_base,
        inner_socket_cut,
        "top shell outline socket opening",
    )

    return shell_base
