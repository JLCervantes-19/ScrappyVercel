"""Gunicorn entrypoint for Railway deployments."""

from app import app  # noqa: F401 - re-export for gunicorn

__all__ = ["app"]
