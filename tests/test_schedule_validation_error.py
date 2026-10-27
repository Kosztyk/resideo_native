import pytest

from custom_components.resideo_native.protocol.validation_error import schedule_validation_detail


def test_known_validation_message_is_redacted():
    text = '{"Message":"Invalid periodType for T6-parent at user@example.com", "private":"do-not-include"}'
    detail = schedule_validation_detail(text, ['T6-parent'])
    assert 'Invalid periodType' in detail
    assert 'T6-parent' not in detail
    assert 'user@example.com' not in detail
    assert 'do-not-include' not in detail


def test_validation_maps_and_non_json():
    assert 'required' in schedule_validation_detail('{"ModelState":{"request.field":["field is required"]}}')
    assert 'No JSON' in schedule_validation_detail('<html>private page</html>')


def test_validation_details_are_bounded():
    detail = schedule_validation_detail('{"message":"' + 'x' * 5000 + '"}')
    assert len(detail) <= 1200


@pytest.mark.parametrize("path", ["api/v3/locations/123/ThermostatSchedule", "api/v2/locations/123/Schedule/Status"])
async def test_http_400_schedule_includes_server_reason_without_token(path):
    from unittest.mock import AsyncMock, MagicMock
    import pytest
    from custom_components.resideo_native.protocol.client import NativeClient
    from custom_components.resideo_native.protocol.errors import CommandError
    response = MagicMock()
    response.status = 400
    response.text = AsyncMock(return_value='{"Message":"Invalid scheduleSubType; private-token-value"}')
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request.return_value = context
    auth = MagicMock()
    auth.access_token = AsyncMock(return_value='private-token-value')
    client = NativeClient(session, auth)
    with pytest.raises(CommandError, match='Invalid scheduleSubType') as err:
        await client._request('PUT', path, {})
    assert 'private-token-value' not in str(err.value)
    assert session.request.call_count == 1
