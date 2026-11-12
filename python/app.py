"""The reference host (honest-page-architecture.md §10.4): import the composition root and call it.

Everything the server is now lives inside the honest-page package: the request path, the token
stylesheet and templates it ships, and the factory that assembles them. A host application is this
small — it imports create_app and hands the returned instance to an ASGI server:

    uv run uvicorn app:app --reload

This file is the named host §10.4 describes. An adopter's own host is the same two lines; the
scaffolding command (spec §12.2) writes them.
"""

from honest_page import create_app

app = create_app()
