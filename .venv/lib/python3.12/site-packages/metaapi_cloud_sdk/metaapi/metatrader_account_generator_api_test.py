import pytest
from mock import AsyncMock, MagicMock

from .metatrader_account_credentials import MetatraderAccountCredentials
from .metatrader_account_generator_api import MetatraderAccountGeneratorApi
from ..clients.metaapi.metatrader_account_generator_client import (
    MetatraderAccountGeneratorClient,
    NewMT4DemoAccount,
    NewMT5DemoAccount,
    MetatraderAccountCredentialsDto,
)


class MockClient(MetatraderAccountGeneratorClient):
    def create_mt4_demo_account(self, account: NewMT4DemoAccount, profile_id: str) -> MetatraderAccountCredentialsDto:
        pass

    def create_mt5_demo_account(self, account: NewMT5DemoAccount, profile_id: str) -> MetatraderAccountCredentialsDto:
        pass


client = MockClient(MagicMock(), MagicMock())
api = MetatraderAccountGeneratorApi(client)


@pytest.fixture(autouse=True)
async def run_around_tests():
    global api
    api = MetatraderAccountGeneratorApi(client)
    yield


class TestMetatraderAccountApi:
    @pytest.mark.asyncio
    async def test_create_mt4_demo(self):
        """Should create MT4 demo account."""
        expected = {
            'login': '12345',
            'password': 'qwerty',
            'serverName': 'HugosWay-Demo3',
            'investorPassword': 'qwerty',
        }
        client.create_mt4_demo_account = AsyncMock(return_value=expected)
        api = MetatraderAccountGeneratorApi(client)
        new_account_data = {'balance': 10, 'email': 'test@test.com', 'leverage': 15, 'serverName': 'server'}
        account = await api.create_mt4_demo_account(new_account_data, 'profileId1')
        assert account.login == expected['login']
        assert account.password == expected['password']
        assert account.server_name == expected['serverName']
        assert account.investor_password == expected['investorPassword']
        assert isinstance(account, MetatraderAccountCredentials)
        client.create_mt4_demo_account.assert_called_with(new_account_data, 'profileId1')

    @pytest.mark.asyncio
    async def test_create_mt5_demo(self):
        """Should create MT5 demo account."""
        expected = {
            'login': '12345',
            'password': 'qwerty',
            'serverName': 'HugosWay-Demo3',
            'investorPassword': 'qwerty',
        }
        client.create_mt5_demo_account = AsyncMock(return_value=expected)
        api = MetatraderAccountGeneratorApi(client)
        new_account_data = {'balance': 10, 'email': 'test@test.com', 'leverage': 15, 'serverName': 'server'}
        account = await api.create_mt5_demo_account(new_account_data, 'profileId2')
        assert account.login == expected['login']
        assert account.password == expected['password']
        assert account.server_name == expected['serverName']
        assert account.investor_password == expected['investorPassword']
        assert isinstance(account, MetatraderAccountCredentials)
        client.create_mt5_demo_account.assert_called_with(new_account_data, 'profileId2')
