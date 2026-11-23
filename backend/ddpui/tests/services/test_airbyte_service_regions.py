"""abreq: per-region server, session reuse, 401 refresh"""

import os
from unittest.mock import MagicMock, patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ddpui.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from ninja.errors import HttpError

from ddpui.ddpairbyte import airbyte_service
from ddpui.ddpairbyte.airbyte_service import abreq, get_sources
from ddpui.tests.conftest import TEST_SECRET_AF


def _response(status_code=200, body=None):
    res = MagicMock()
    res.status_code = status_code
    res.headers = {"Content-Type": "application/json"}
    res.json.return_value = body if body is not None else {"ok": True}
    if status_code >= 400:
        res.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    res.text = str(body)
    return res


def test_abreq_uses_server_url_and_token(airbyte_server_af):
    session = MagicMock()
    session.request.return_value = _response()
    with patch.object(airbyte_service, "_session_for", return_value=session):
        assert abreq("sources/list", {"workspaceId": "w"}, server=airbyte_server_af) == {"ok": True}
    session.request.assert_called_once_with(
        "POST",
        "https://airbyte-af-staging-internal.dalgo.org:443/api/v1/sources/list",
        headers={"Authorization": "Basic af-token-value"},
        json={"workspaceId": "w"},
        timeout=30,
    )


def test_abreq_get_and_timeout(airbyte_server_in):
    session = MagicMock()
    session.request.return_value = _response()
    with patch.object(airbyte_service, "_session_for", return_value=session):
        abreq("instance_configuration", method="GET", timeout=5, server=airbyte_server_in)
    args, kwargs = session.request.call_args
    assert args == ("GET", "http://airbyte-in.example.org:8000/api/v1/instance_configuration")
    assert kwargs["timeout"] == 5


def test_public_function_forwards_server(airbyte_server_af):
    with patch.object(airbyte_service, "abreq", return_value={"sources": []}) as mock_abreq:
        get_sources("w", server=airbyte_server_af)
    assert mock_abreq.call_args.kwargs["server"] is airbyte_server_af


def test_401_invalidates_and_retries_once(airbyte_server_af, mock_region_secrets):
    session = MagicMock()
    session.request.side_effect = [_response(401, {"message": "unauthorized"}), _response()]
    with patch.object(airbyte_service, "_session_for", return_value=session), patch(
        "ddpui.ddpairbyte.airbyte_service.airbyte_credentials.invalidate"
    ) as mock_invalidate:
        result = abreq("sources/list", {}, server=airbyte_server_af)
    assert result == {"ok": True}
    assert session.request.call_count == 2
    mock_invalidate.assert_called_once_with(TEST_SECRET_AF)
    # the retry was made with freshly loaded credentials
    mock_region_secrets.get_secret_value.assert_called_once_with(SecretId=TEST_SECRET_AF)


def test_second_401_raises(airbyte_server_af, mock_region_secrets):
    session = MagicMock()
    session.request.side_effect = [_response(401), _response(401)]
    with patch.object(airbyte_service, "_session_for", return_value=session):
        with pytest.raises(HttpError) as excinfo:
            abreq("sources/list", {}, server=airbyte_server_af)
    assert excinfo.value.status_code == 401
    assert session.request.call_count == 2


def test_session_reused_per_region(airbyte_server_in, airbyte_server_af):
    assert airbyte_service._session_for(airbyte_server_af) is airbyte_service._session_for(
        airbyte_server_af
    )
    assert airbyte_service._session_for(airbyte_server_af) is not airbyte_service._session_for(
        airbyte_server_in
    )


def test_token_not_logged(airbyte_server_af):
    session = MagicMock()
    session.request.return_value = _response()
    with patch.object(airbyte_service, "_session_for", return_value=session), patch.object(
        airbyte_service, "logger"
    ) as mock_logger:
        abreq("sources/list", {}, server=airbyte_server_af)
    for call in mock_logger.mock_calls:
        assert "af-token-value" not in str(call)
