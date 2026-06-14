"""Optional HTTP read API (requires the [api] extra: FastAPI + uvicorn).

Importing this package pulls in FastAPI; the base CLI keeps it out of the import
graph and only loads it inside the serve-api handler.
"""

from .app import create_app

__all__ = ["create_app"]
