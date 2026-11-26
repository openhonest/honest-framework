# scenario: render_file is available as an honest_render public export
# inherits: hd=python/honest-render/honest-render.hd::render_file -> feature=specs/features/honest-render.feature::render_file is available as an honest_render public export
import honest_render


_EXPECTED = {"render_file"}


def probe_render_file_public_export():
    """Check the declared sole door and an explicit internal import."""
    failures = []
    actual = honest_render.__all__
    if set(actual) != _EXPECTED or len(actual) != len(_EXPECTED):
        failures.append(
            f"honest_render.__all__ must contain exactly {sorted(_EXPECTED)!r}, got {actual!r}"
        )
    if not callable(getattr(honest_render, "render_file", None)):
        failures.append("honest_render.render_file is missing or not callable")
    try:
        from honest_render import render_markdown
    except ImportError as exc:
        failures.append(f"existing named import honest_render.render_markdown failed: {exc}")
    else:
        if not callable(render_markdown):
            failures.append("explicitly imported honest_render.render_markdown is not callable")
    return failures
