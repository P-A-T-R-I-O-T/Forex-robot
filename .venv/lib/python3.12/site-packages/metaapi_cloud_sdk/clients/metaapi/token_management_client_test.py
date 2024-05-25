import pytest
import respx
from httpx import Response
from mock import MagicMock, AsyncMock

from .token_management_client import TokenManagementClient
from ..http_client import HttpClient

PROFILE_API_URL = 'https://profile-api-v1.agiliumtrade.agiliumtrade.ai'
http_client = HttpClient()
token = 'header.payload.sign'
account_token = 'token'
domain_client: MagicMock = None
token_management_client: TokenManagementClient = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    global http_client
    http_client = HttpClient()
    global domain_client
    domain_client = MagicMock()
    domain_client.token = token
    domain_client.domain = 'agiliumtrade.agiliumtrade.ai'
    domain_client.get_url = AsyncMock(return_value=PROFILE_API_URL)
    global token_management_client
    token_management_client = TokenManagementClient(http_client, domain_client)


class TestTokenManagementClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_access_rules(self):
        """Should retrieve access rules manifest from API."""
        expected = [
            {
                'id': 'trading-account-management-api',
                'description': 'Trading account management API',
                'application': 'trading-account-management-api',
                'services': [{'description': 'REST API', 'service': 'rest'}],
                'methodGroups': [
                    {
                        'description': 'All method groups',
                        'group': '*',
                        'methods': [{'description': 'All methods', 'method': '*'}],
                    }
                ],
                'roles': [{'description': 'Read-only access to resources', 'roles': ['reader']}],
                'entities': [{'description': 'All entities', 'entity': '*'}],
            }
        ]
        rsps = respx.get(f'{PROFILE_API_URL}/access-rule-manifest').mock(return_value=Response(200, json=expected))
        manifest = await token_management_client.get_access_rules()
        assert rsps.calls[0].request.url == f'{PROFILE_API_URL}/access-rule-manifest'
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert manifest == expected

    @pytest.mark.asyncio
    async def test_not_retrieve_access_rules_with_account_token(self):
        """Should not retrieve access rules manifest from API with account token."""
        domain_client.token = account_token
        token_management_client = TokenManagementClient(http_client, domain_client)
        try:
            await token_management_client.get_access_rules()
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke get_access_rules method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_narrow_down_token(self):
        """Should narrow down token via API."""
        payload = {
            'accessRules': [
                {
                    'id': 'trading-account-management-api',
                    'application': 'trading-account-management-api',
                    'service': 'rest',
                    'resources': [{'entity': 'account', 'id': 'accountId'}],
                    'methodGroups': [{'group': 'account-management', 'methods': [{'method': 'getAccount'}]}],
                    'roles': ['reader'],
                }
            ]
        }
        expected = {'token': 'token'}
        rsps = respx.post(f'{PROFILE_API_URL}/users/current/narrow-down-auth-token').mock(
            return_value=Response(200, json=expected)
        )
        response = await token_management_client.narrow_down_token(payload)
        assert response['token'] == expected['token']
        assert rsps.calls[0].request.url == f'{PROFILE_API_URL}/users/current/narrow-down-auth-token'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @respx.mock
    @pytest.mark.asyncio
    async def test_narrow_down_token_with_validity_hours(self):
        """Should narrow down token via API."""
        payload = {
            'accessRules': [
                {
                    'id': 'trading-account-management-api',
                    'application': 'trading-account-management-api',
                    'service': 'rest',
                    'resources': [{'entity': 'account', 'id': 'accountId'}],
                    'methodGroups': [{'group': 'account-management', 'methods': [{'method': 'getAccount'}]}],
                    'roles': ['reader'],
                }
            ]
        }
        validity_in_hours = 5
        expected = {'token': 'token'}
        rsps = respx.post(f'{PROFILE_API_URL}/users/current/narrow-down-auth-token').mock(
            return_value=Response(200, json=expected)
        )
        response = await token_management_client.narrow_down_token(payload, validity_in_hours)
        assert response['token'] == expected['token']
        assert (
            rsps.calls[0].request.url == f'{PROFILE_API_URL}/users/current/narrow-down-auth-token?validity-in-hours=5'
        )
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_narrow_down_token_with_account_token(self):
        """Should not retrieve access rules manifest from API with account token."""
        domain_client.token = account_token
        token_management_client = TokenManagementClient(http_client, domain_client)
        try:
            await token_management_client.narrow_down_token({})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke narrow_down_token method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )
