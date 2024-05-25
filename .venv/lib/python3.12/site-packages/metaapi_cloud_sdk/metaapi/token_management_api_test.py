import base64
import json
from typing import Union

import pytest
from httpx import Response
from mock import AsyncMock, MagicMock

from .token_management_api import TokenManagementApi
from ..clients.metaapi.token_management_client import (
    NarrowDownAccessRules,
    NarrowDownSimplifiedAccessRules,
    TokenManagementClient,
)


class MockClient(TokenManagementClient):
    def get_access_rules(self) -> Response:
        pass

    def narrow_down_token(
        self,
        narrow_down_payload: Union[NarrowDownAccessRules, NarrowDownSimplifiedAccessRules],
        validity_in_hours: float = None,
    ) -> Response:
        pass


client = MockClient(MagicMock(), MagicMock())
api = TokenManagementApi(client)


@pytest.fixture(autouse=True)
async def run_around_tests():
    global api
    api = TokenManagementApi(client)
    yield


class TestTokenManagementApi:
    @pytest.mark.asyncio
    async def test_retrieve_access_rules(self):
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
        client.get_access_rules = AsyncMock(return_value=expected)
        api = TokenManagementApi(client)
        manifest = await api.get_access_rules()
        assert manifest == expected
        client.get_access_rules.assert_called_once()

    @pytest.mark.asyncio
    async def test_narrow_down_token(self):
        """Should narrow down token."""
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
        client.narrow_down_token = AsyncMock(return_value={'token': 'token'})
        api = TokenManagementApi(client)
        token = await api.narrow_down_token(payload)
        assert token == 'token'
        client.narrow_down_token.assert_called_once_with(payload, None)

    @pytest.mark.asyncio
    async def test_narrow_down_token_simplified_api(self):
        """Should narrow down token to speciffic applications, roles and resources with validity."""
        payload = {
            'applications': ['trading-account-management-api'],
            'roles': ['reader'],
            'resources': [{'entity': 'account', 'id': 'accountId'}],
        }
        validity_in_hours = 12
        client.narrow_down_token = AsyncMock(return_value={'token': 'token'})
        api = TokenManagementApi(client)
        token = await api.narrow_down_token(payload, validity_in_hours)
        assert token == 'token'
        client.narrow_down_token.assert_called_once_with(payload, validity_in_hours)

    @pytest.mark.asyncio
    async def test_narrow_down_token_applications(self):
        """Should narrow down token applications."""
        applications = ['trading-account-management-api', 'metastats-api']
        validity_in_hours = 3
        client.narrow_down_token = AsyncMock(return_value={'token': 'token'})
        api = TokenManagementApi(client)
        token = await api.narrow_down_token_applications(applications, validity_in_hours)
        assert token == 'token'
        client.narrow_down_token.assert_called_once_with({'applications': applications}, validity_in_hours)

    @pytest.mark.asyncio
    async def test_narrow_down_token_roles(self):
        """Should narrow down token roles."""
        roles = ['reader']
        validity_in_hours = 10
        client.narrow_down_token = AsyncMock(return_value={'token': 'token'})
        api = TokenManagementApi(client)
        token = await api.narrow_down_token_roles(roles, validity_in_hours)
        assert token == 'token'
        client.narrow_down_token.assert_called_once_with({'roles': roles}, validity_in_hours)

    @pytest.mark.asyncio
    async def test_narrow_down_token_resources(self):
        """Should narrow down token resources."""
        resources = [{'entity': 'account', 'id': 'accountId'}]
        validity_in_hours = 12
        client.narrow_down_token = AsyncMock(return_value={'token': 'token'})
        api = TokenManagementApi(client)
        token = await api.narrow_down_token_resources(resources, validity_in_hours)
        assert token == 'token'
        client.narrow_down_token.assert_called_once_with({'resources': resources}, validity_in_hours)

    @pytest.mark.asyncio
    async def test_resources_narrowed_down(self):
        """Should check and return true when token resources are narrowed down."""
        payload = {
            'accessRules': [
                {
                    'methods': ['trading-account-management-api:rest:public:*:*'],
                    'roles': ['reader'],
                    'resources': ['account:$USER_ID$:*'],
                },
                {
                    'methods': ['metaapi-api:rest:public:*:*'],
                    'roles': ['reader'],
                    'resources': ['account:$USER_ID$:*', 'tracker:$USER_ID$:id123'],
                },
            ]
        }
        token = "." + base64.b64encode(json.dumps(payload).encode()).decode() + "."
        areResourcesNarrowedDown = api.are_token_resources_narrowed_down(token)
        assert areResourcesNarrowedDown is True

    @pytest.mark.asyncio
    async def test_resources_not_narrowed_down(self):
        """Should check and return false when token resources are not narrowed down."""
        payload = {
            'accessRules': [
                {
                    'methods': ['trading-account-management-api:rest:public:*:*'],
                    'roles': ['reader'],
                    'resources': ['*:$USER_ID$:*'],
                },
                {'methods': ['metaapi-api:rest:public:*:*'], 'roles': ['reader'], 'resources': ['*:$USER_ID$:*']},
            ]
        }
        token = "." + base64.b64encode(json.dumps(payload).encode()).decode() + "."
        areResourcesNarrowedDown = api.are_token_resources_narrowed_down(token)
        assert areResourcesNarrowedDown is False
