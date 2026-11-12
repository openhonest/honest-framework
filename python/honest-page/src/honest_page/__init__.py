"""honest-page: the host-page structural contract and its reference application (spec §10).

The request path turns a typed request into a rendered page: the pure core (extract_tokens,
search_chain, page_context), the orchestrators that run one path each (build_manifest, run_search,
build_home), and the three HTTP doors (intake, index, search). The composition root assembles the
application FastAPI runs (read_bundle, route_table, assembly, install, build_app, create_app). The SSE
extension hook lets a custom module register its own stream source against one declared surface
(surface_slot, register_source, attach, attach_stream).
"""

from honest_page.factory import assembly, build_app, create_app, install, read_bundle, route_table
from honest_page.hook import attach, attach_stream, register_source, surface_slot
from honest_page.request import (
    build_home,
    build_manifest,
    extract_tokens,
    index,
    intake,
    page_context,
    run_search,
    search,
    search_chain,
)

__all__ = [
    # Request path — pure core
    "extract_tokens",
    "search_chain",
    "page_context",
    # Request path — orchestrators
    "build_manifest",
    "run_search",
    "build_home",
    # Request path — doors
    "intake",
    "index",
    "search",
    # Composition root
    "read_bundle",
    "route_table",
    "assembly",
    "install",
    "build_app",
    "create_app",
    # SSE extension hook
    "surface_slot",
    "register_source",
    "attach",
    "attach_stream",
]
