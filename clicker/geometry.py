import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

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

    shell_base = create_top_shell_base(
        top_mesh=top_mesh,
        reference_mesh=mesh,
        slice_z=slice_z,
        cfg=cfg,
    )

    shell_base = cut_bottom_switch_cavity(
        shell_base,
        mesh,
        slice_z,
        cfg,
    )

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


def get_slice_outline_polygon(reference_mesh: trimesh.Trimesh, slice_z: float):
    section = reference_mesh.section(
        plane_origin=[0, 0, slice_z],
        plane_normal=[0, 0, 1],
    )

    if section is None:
        raise ValueError("Could not create outline from slice plane.")

    polygons = []

    for path in section.discrete:
        if len(path) < 3:
            continue

        points_2d = [(float(p[0]), float(p[1])) for p in path]

        if points_2d[0] != points_2d[-1]:
            points_2d.append(points_2d[0])

        polygon = Polygon(points_2d)

        if polygon.is_valid and polygon.area > 0:
            polygons.append(polygon)

    if not polygons:
        raise ValueError("Could not create a closed outline from the slice.")

    outline = unary_union(polygons)

    if isinstance(outline, MultiPolygon):
        outline = max(outline.geoms, key=lambda p: p.area)

    return outline


def extrude_polygon_down(polygon, top_z: float, depth: float):
    mesh = trimesh.creation.extrude_polygon(polygon, height=depth)
    mesh.apply_translation([0, 0, top_z - depth])
    return mesh


def create_top_shell_base(
    top_mesh: trimesh.Trimesh,
    reference_mesh: trimesh.Trimesh,
    slice_z: float,
    cfg: dict,
):
    wall_thickness = cfg["shell_wall_thickness"]
    base_floor = cfg["shell_base_floor"]

    insert_depth = cfg.get("shell_insert_depth", cfg["shell_wall_height"])
    insert_clearance = cfg.get("shell_insert_clearance", 0.35)
    outline_padding = cfg.get("shell_outline_padding", 0.5)

    total_depth = insert_depth + cfg["bottom_cavity_depth"] + base_floor

    outline = get_slice_outline_polygon(reference_mesh, slice_z)

    inner_outline = outline.buffer(
        insert_clearance,
        join_style=2,
    )

    outer_outline = outline.buffer(
        insert_clearance + wall_thickness + outline_padding,
        join_style=2,
    )

    outer_base = extrude_polygon_down(
        outer_outline,
        top_z=slice_z,
        depth=total_depth,
    )

    insert_cavity_cutter = extrude_polygon_down(
        inner_outline,
        top_z=slice_z + 1.0,
        depth=insert_depth + 1.5,
    )

    shell_base = safe_boolean_difference(
        outer_base,
        insert_cavity_cutter,
        "top clicker insert cavity",
    )

    return shell_base
