"""
Configuration defaults for the STL to Cherry MX Clicker Converter.
"""

APP_VERSION = "v2.2.8"

DEFAULTS = {
    # Top half / switch stem side
    "housing_size": 16.0,
    "housing_depth": 5.2,
    "cross_width": 4.20,
    "cross_arm": 1.45,
    "cross_depth": 4.2,
    "stem_tolerance": 0.30,
    "top_circular_clearance": 1.20,  # diameter is cross width + tolerance + this value

    # Cavity placement
    "cavity_x_offset": 0.0,
    "cavity_y_offset": 0.0,

    # Bottom half / switch body side
    "bottom_cavity_size": 15.0,
    "bottom_cavity_depth": 8.2,
    "center_hole_dia": 4.00,
    "center_hole_tolerance": 0.30,
    "center_support_outer_dia": 7.00,
}
