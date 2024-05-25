import asyncio
from asyncio import sleep

import pytest
import respx
from freezegun import freeze_time
from httpx import Response
from mock import AsyncMock, MagicMock, patch

from .client_api_client import ClientApiClient
from ..http_client import HttpClient

CLIENT_API_URL = 'https://mt-client-api-v1.agiliumtrade.agiliumtrade.ai'
token = 'header.payload.sign'
http_client = HttpClient()
client_api_client: ClientApiClient = None
expected = None
domain_client: MagicMock = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    global expected
    expected = {
        'g1': {'specification': ['description'], 'position': ['time'], 'order': ['expirationTime']},
        'g2': {'specification': ['pipSize'], 'position': ['comment'], 'order': ['brokerComment']},
    }
    global http_client
    http_client = HttpClient()
    global domain_client
    domain_client = MagicMock()
    domain_client.token = token
    domain_client.domain = 'agiliumtrade.agiliumtrade.ai'
    domain_client.get_url = AsyncMock(return_value=CLIENT_API_URL)
    global client_api_client
    client_api_client = ClientApiClient(http_client, domain_client)
    yield


class TestClientApiClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve(self):
        """Should retrieve hashing ignored field lists."""
        expected_2 = {
            'g1': {'specification': ['startTime'], 'position': ['profit'], 'order': ['currentPrice']},
            'g2': {'specification': ['pipSize'], 'position': ['comment'], 'order': ['brokerComment']},
        }
        rsps = respx.get(f'{CLIENT_API_URL}/hashing-ignored-field-lists').mock(
            return_value=Response(200, json=expected)
        )

        try:
            client_api_client.get_hashing_ignored_field_lists('vint-hill')
            pytest.fail()
        except Exception as error:
            assert error.args[0] == "Ignored field lists for region vint-hill not found."

        try:
            client_api_client.get_hashing_ignored_field_lists('combined')
            pytest.fail()
        except Exception as error:
            assert error.args[0] == "Ignored field lists not found."

        await client_api_client.refresh_ignored_field_lists('vint-hill')

        ignored_fields = client_api_client.get_hashing_ignored_field_lists('vint-hill')
        assert ignored_fields == expected

        combined_ignored_fields = client_api_client.get_hashing_ignored_field_lists('combined')

        assert combined_ignored_fields == expected

        assert rsps.calls[0].request.url == f'{CLIENT_API_URL}/hashing-ignored-field-lists'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        domain_client.get_url.assert_called_once_with('https://mt-client-api-v1', 'vint-hill')

        await client_api_client.refresh_ignored_field_lists('vint-hill')

        assert rsps.call_count == 1

        try:
            client_api_client.get_hashing_ignored_field_lists('new-york')
            pytest.fail()
        except Exception as error:
            assert error.args[0] == "Ignored field lists for region new-york not found."

        rsps.mock(return_value=Response(200, json=expected_2))
        await client_api_client.refresh_ignored_field_lists('new-york')

        assert rsps.call_count == 2

        combined_ignored_fields = client_api_client.get_hashing_ignored_field_lists('combined')

        assert combined_ignored_fields == expected_2

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_when_caching_time_expired(self):
        """Should update data when caching time expired."""
        with patch('lib.clients.metaapi.client_api_client.asyncio.sleep', new=lambda x: sleep(x / 60)):
            with freeze_time() as frozen_datetime:
                expected_2 = {
                    'g1': {'specification': ['startTime'], 'position': ['profit'], 'order': ['currentPrice']},
                    'g2': {'specification': ['pipSize'], 'position': ['comment'], 'order': ['brokerComment']},
                }
                rsps = respx.get(f'{CLIENT_API_URL}/hashing-ignored-field-lists').mock(
                    return_value=Response(200, json=expected)
                )
                await client_api_client.refresh_ignored_field_lists('vint-hill')
                ignored_fields = client_api_client.get_hashing_ignored_field_lists('vint-hill')
                assert ignored_fields == expected
                rsps.mock(return_value=Response(200, json=expected_2))
                frozen_datetime.tick(3660)
                await sleep(3.66)
                ignored_fields_2 = client_api_client.get_hashing_ignored_field_lists('vint-hill')
                assert ignored_fields_2 == expected_2
                assert rsps.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_one_request_if_two_sync(self):
        """Should send one request if two concurrent synchronizations."""
        rsps = respx.get(f'{CLIENT_API_URL}/hashing-ignored-field-lists').mock(
            return_value=Response(200, json=expected)
        )
        await asyncio.gather(
            *[
                asyncio.create_task(client_api_client.refresh_ignored_field_lists('vint-hill')),
                asyncio.create_task(client_api_client.refresh_ignored_field_lists('vint-hill')),
            ]
        )
        ignored_fields = client_api_client.get_hashing_ignored_field_lists('vint-hill')
        assert ignored_fields == expected

        assert rsps.calls[0].request.url == f'{CLIENT_API_URL}/hashing-ignored-field-lists'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        domain_client.get_url.assert_called_once_with('https://mt-client-api-v1', 'vint-hill')

        assert rsps.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_retry_request_if_received_error(self):
        """Should retry request if received error."""
        with patch('lib.clients.metaapi.client_api_client.asyncio.sleep', new=lambda x: sleep(x / 60)):
            call_number = 0

            def request_stub(opts1, opts2):
                nonlocal call_number
                call_number += 1
                if call_number < 3:
                    raise Exception('test')
                else:
                    return expected

            client_api_client._http_client.request = AsyncMock(side_effect=request_stub)

            asyncio.create_task(client_api_client.refresh_ignored_field_lists('vint-hill'))
            asyncio.create_task(client_api_client.refresh_ignored_field_lists('vint-hill'))

            await sleep(1)

            ignored_fields = client_api_client.get_hashing_ignored_field_lists('vint-hill')
            assert ignored_fields == expected
            assert client_api_client._http_client.request.call_count == 3
