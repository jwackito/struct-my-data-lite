"""Edition install seam (spec 24).

Lite registers nothing. Cloud replaces this body with router includes and hook
registrations so that shared files stay identical across editions.
"""

from fastapi import FastAPI


def install(app: FastAPI) -> None:
    """Wire edition-specific routers and hooks into the application."""
