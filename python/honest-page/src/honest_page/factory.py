"""The composition root (honest-page-architecture.md §10.4): the application factory FastAPI runs.

create_app is the one point a host calls. It hands off to build_app, which pulls the shipped bundle,
declares the route map as data, lays out the assembly, and installs it. The pieces stay separable and
declared: read_bundle reads the bundled directories, route_table returns the route map as module-level
data a tool reads by parsing, assembly packs the mount plan, and install is the one HTTP write — it
creates the application object and applies the plan. The honest-py realization uses FastAPI; a host
serves the returned instance with any ASGI server.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from honest_page.request import index, intake, search

_HERE = Path(__file__).parent

# The handlers the route map names, resolved by the name route_table records. Module-level data, so a
# tool reads the binding without calling the factory.
_HANDLERS = {
    "index": index,
    "search": search,
}


def read_bundle():
    """The shipped template and static directories, as they ship inside the package (§10.4). A reader
    of the filesystem: the one thing the factory needs that no caller hands it."""
    return {
        "template_dir": str(_HERE / "templates"),
        "static_dir": str(_HERE / "static"),
    }


def route_table():
    """The route map as data (§9, §10.2): one entry per route, each pairing a method and path with the
    handler that path runs. Module-level data honest-check reads by parsing, never by calling the
    factory, so it resolves a path to its chain without running the application."""
    return [
        {"method": "GET", "path": "/", "chain": "index"},
        {"method": "GET", "path": "/search", "chain": "search"},
    ]


def assembly(bundle, routes):
    """Lay out what the factory mounts, in order (§10.4): the static directory, the template directory,
    and the route map. Pure: the bundle's directories and the route table packed into one plan."""
    return {
        "static_dir": bundle["static_dir"],
        "template_dir": bundle["template_dir"],
        "routes": routes,
    }


def install(plan):
    """Create the application object and apply the plan (§10.4): mount static so the token stylesheet
    and client scripts load, register the template environment, install the intake middleware ahead of
    every route, and register one handler per route-map entry. Returns the application the ASGI server
    runs. The one HTTP write: FastAPI is the Python driver, served by any ASGI host."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=plan["static_dir"]), name="static")
    app.state.templates = Jinja2Templates(directory=plan["template_dir"])
    app.middleware("http")(intake)
    for entry in plan["routes"]:
        app.add_api_route(entry["path"], _HANDLERS[entry["chain"]], methods=[entry["method"]], response_class=HTMLResponse)
    return app


def build_app():
    """Assemble the application from its parts (§10.4): pull the bundle, declare the routes, lay out the
    assembly, and install it."""
    bundle = read_bundle()
    routes = route_table()
    plan = assembly(bundle, routes)
    return install(plan)


def create_app():
    """The composition root the host calls (§10.4): hand off to build_app and return the application the
    ASGI server runs. `from honest_page import create_app; app = create_app()`."""
    return build_app()
