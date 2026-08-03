from web.api.deps import _luminance, glow_safe


def test_luminance_bounds():
    assert _luminance("#000000") == 0.0
    assert abs(_luminance("#ffffff") - 1.0) < 1e-9


def test_glow_safe_lifts_dark_colors():
    lifted = glow_safe("#000000")
    assert _luminance(lifted) >= 0.35


def test_glow_safe_leaves_bright_colors_alone():
    assert glow_safe("#ffb612") == "#ffb612"  # Steelers gold is already bright


def test_glow_safe_output_is_hex():
    out = glow_safe("#03202f")
    assert out.startswith("#") and len(out) == 7
