"""
Core clicker geometry generation.

This module contains no Streamlit UI code so it can be tested independently.
"""

import trimesh

from .mesh_utils import make_box, make_cylinder, safe_boolean_difference


def generate_clicker_parts(mesh: trimesh.Trimesh, slice_z: float, cfg: dict):
    center = mesh.bounds.mean(axis=0)
    cavity_x = center[0] + cfg.get("cavity_x_offset", 0.0)
    cavity_y = center[1] + cfg.get("cavity_y_offset", 0.0)

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
        [cavity_x, cavity_y, top_cut_z],
    )

    circular_boss_dia = max(cross_width, cross_arm) + cfg["top_circular_clearance"]
    circular_keepout = make_cylinder(
        circular_boss_dia,
        housing_depth + 0.20,
        [cavity_x, cavity_y, top_cut_z],
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
        [cavity_x, cavity_y, cross_z],
    )
    horizontal_cross = make_box(
        cross_width,
        cross_arm,
        cross_depth,
        [cavity_x, cavity_y, cross_z],
    )

    top_result = safe_boolean_difference(top_result, vertical_cross, "vertical MX stem cross")
    top_result = safe_boolean_difference(top_result, horizontal_cross, "horizontal MX stem cross")

    # ---------- BOTTOM HALF ----------
    # Goal: universal bottom cavity. Remove the switch-body pocket while keeping
    # a center cylindrical support, then cut the center hole through that support.
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

    # Keep a center support pillar inside the universal cavity.
    # The pillar is intentionally only half the height of the total cavity:
    # it rises from the bottom of the pocket to the midpoint, leaving the
    # upper half open so the switch body has more clearance.
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
    bottom_result = safe_boolean_difference(bottom_result, bottom_pocket_cutter, "bottom universal cavity")

    # Cut only the center pin hole. It is no deeper than the large cavity.
    center_hole_dia = cfg["center_hole_dia"] + cfg["center_hole_tolerance"]
    center_hole_depth = bottom_cavity_depth
    center_hole_z = slice_z - center_hole_depth / 2
    center_hole = make_cylinder(
        center_hole_dia,
        center_hole_depth,
        [cavity_x, cavity_y, center_hole_z],
    )
    bottom_result = safe_boolean_difference(bottom_result, center_hole, "bottom center pin hole")

    return top_result, bottom_result
