"""
honest-py application scaffold.

Wires together:
  - FastAPI
  - honest-type intake middleware (token classification at the boundary)
  - Jinja2 templates (base.html / page.html)
  - honest-persist connection pool
  - honest-alerts SSE stream endpoint
  - Static file serving for theme.css and app assets

Replace the vocabulary, binding, and route handlers with your own.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from honest_type import vocabulary, binding, predicate, classify

# ---------------------------------------------------------------------------
# Application vocabulary and binding
# Declare what tokens this application accepts and where they land.
# Every HTTP request passes through classify() before reaching a handler.
# ---------------------------------------------------------------------------

app_vocab = vocabulary({
    "resource":  {"items", "users", "settings"},
    "action":    {"list", "create", "update", "delete", "search"},
    "uuid":      predicate(lambda s: len(s) == 36 and s[8] == "-"),
    "integer":   predicate(lambda s: s.isdigit()),
    "boolean":   {"true", "false"},
})

app_binding = binding({
    "resource":  "resource",
    "action":    "action",
    "uuid":      "id",
    "integer":   "page",
    "boolean":   "flag",
})

# ---------------------------------------------------------------------------
# Connection pool (honest-persist)
# ---------------------------------------------------------------------------

_pool = None

def get_pool():
    return _pool

# ---------------------------------------------------------------------------
# Lifespan: startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    # from honest.persist import create_pool
    # _pool = await create_pool(config)
    yield
    # if _pool:
    #     await _pool.close()

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# ---------------------------------------------------------------------------
# honest-type intake middleware
# Classifies and binds request parameters before they reach handlers.
# Handlers receive request.state.manifest — a plain dict of typed slots.
# Unrecognized tokens produce rejections in the manifest; they do not throw.
# ---------------------------------------------------------------------------

@app.middleware("http")
async def intake(request: Request, call_next):
    tokens = [
        *request.path_params.values(),
        *request.query_params.values(),
    ]
    manifest = classify(tokens, app_vocab, app_binding)

    if manifest.get("_rejections") and request.method != "GET":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"rejected": [r["token"] for r in manifest["_rejections"]]},
        )

    request.state.manifest = manifest
    return await call_next(request)

# ---------------------------------------------------------------------------
# Root: serve the base page
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("page.html", {
        "request":     request,
        "app_name":    "My Honest App",
        "page_title":  "Home",
        "initial_url": "/items",
    })

# ---------------------------------------------------------------------------
# honest-alerts SSE stream
# honest-alerts delivers messages to the browser via this endpoint.
# Replace with honest.alerts.stream(request) when honest-alerts is available.
# ---------------------------------------------------------------------------

@app.get("/api/alerts/stream")
async def alerts_stream(request: Request):
    from fastapi.responses import StreamingResponse
    import asyncio

    async def event_stream():
        # Placeholder: yields a keep-alive comment every 30 seconds.
        # Replace with honest-alerts projection subscription.
        while True:
            if await request.is_disconnected():
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(30)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# ---------------------------------------------------------------------------
# Example fragment route
# Returns an HTML fragment that HTMX swaps into #content-area.
# The manifest from intake is available on request.state.manifest.
# ---------------------------------------------------------------------------

@app.get("/items", response_class=HTMLResponse)
async def list_items(request: Request):
    manifest = request.state.manifest
    # items = await fetch_items(get_pool(), manifest)
    items = []  # replace with honest-persist query
    return templates.TemplateResponse("items.html", {
        "request": request,
        "items":   items,
        "manifest": manifest,
    })
