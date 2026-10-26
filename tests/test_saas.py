"""Tests for the edition install seam (spec 24).

Lite ships a no-op ``install(app)``; cloud replaces the body with router
includes and hook registrations.
"""

import importlib.util

import pytest
from fastapi import FastAPI

from app import saas


def test_install_is_a_noop():
    if importlib.util.find_spec("app.invites.routes") is not None:
        pytest.skip("cloud edition registers routers and hooks")
    app = FastAPI()
    routes_before = len(app.routes)

    assert saas.install(app) is None
    assert len(app.routes) == routes_before


def test_main_imports_install_seam():
    import app.main

    assert app.main.install is saas.install
