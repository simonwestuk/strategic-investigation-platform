"""ASGI entrypoint: ``uvicorn sip.api.main:app``."""

from sip.api.app import create_app

app = create_app()
