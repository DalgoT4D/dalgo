"""Guard: every public airbyte_service function must take a required keyword-only `server`.

A call site that forgets it then fails loudly with TypeError instead of silently reaching
the home (Mumbai) Airbyte for an org in another data region."""

import inspect
import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ddpui.ddpairbyte import airbyte_service

# pure helpers that never talk to Airbyte
NO_SERVER = {"parse_job_info", "clear_sessions"}


def _public_functions():
    return [
        (name, fn)
        for name, fn in inspect.getmembers(airbyte_service, inspect.isfunction)
        if fn.__module__ == airbyte_service.__name__
        and not name.startswith("_")
        and name not in NO_SERVER
    ]


def test_there_are_functions_to_check():
    assert len(_public_functions()) > 40


@pytest.mark.parametrize("name,fn", _public_functions())
def test_server_is_required_keyword_only(name, fn):
    param = inspect.signature(fn).parameters.get("server")
    assert param is not None, f"{name} has no server parameter"
    assert param.kind == inspect.Parameter.KEYWORD_ONLY, f"{name}: server must be keyword-only"
    assert param.default is inspect.Parameter.empty, f"{name}: server must not have a default"
