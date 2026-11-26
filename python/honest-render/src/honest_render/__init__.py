"""honest-render - the public static renderer of one .hd declaration."""

from honest_render.render import (
    build_view,
    draw_diagram,
    read_ir,
    read_source,
    render_declaration,
    render_fault,
    render_file,
    render_markdown,
    write_document,
)

# inherits: hd=python/honest-render/honest-render.hd::render_file -> feature=specs/features/honest-render.feature::render_file is available as an honest_render public export -> test=python/honest-render/conformance/laws_render_file_public_export.py::probe_render_file_public_export
__all__ = ["render_file"]
