import pytest
import respx
from httpx import Response
from mock import MagicMock, AsyncMock, patch

from .metatrader_account_generator_client import MetatraderAccountGeneratorClient
from ..http_client import HttpClient

PROVISIONING_API_URL = 'https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai'
token = 'header.payload.sign'
account_token = 'token'
http_client = HttpClient()
domain_client: MagicMock = None
demo_account_client: MetatraderAccountGeneratorClient = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    global http_client
    http_client = HttpClient()
    global domain_client
    domain_client = MagicMock()
    domain_client.token = token
    domain_client.domain = 'agiliumtrade.agiliumtrade.ai'
    domain_client.get_url = AsyncMock(return_value=PROVISIONING_API_URL)
    global demo_account_client
    demo_account_client = MetatraderAccountGeneratorClient(http_client, domain_client)


class TestMetatraderDemoAccountClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_demo_mt4(self):
        """Should create new MetaTrader 4 demo account."""
        with patch('lib.clients.metaapi.metatrader_account_generator_client.random_id', return_value='transactionId'):
            expected = {
                'login': '12345',
                'password': 'qwerty',
                'serverName': 'HugosWay-Demo3',
                'investorPassword': 'qwerty',
            }
            account = {
                'accountType': 'type',
                'balance': 10,
                'email': 'test@test.com',
                'leverage': 15,
                'serverName': 'HugosWay-Demo3',
            }
            rsps = respx.post(
                f'{PROVISIONING_API_URL}/users/current/provisioning-profiles/profileId1/mt4-demo-accounts'
            ).mock(return_value=Response(200, json=expected))
            accounts = await demo_account_client.create_mt4_demo_account(account, 'profileId1')
            assert (
                rsps.calls[0].request.url
                == f'{PROVISIONING_API_URL}/users/current/provisioning-profiles/' + 'profileId1/mt4-demo-accounts'
            )
            assert rsps.calls[0].request.method == 'POST'
            assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
            assert rsps.calls[0].request.headers['transaction-id'] == 'transactionId'
            assert accounts == expected

    @pytest.mark.asyncio
    async def test_not_create_mt4_demo_with_account_token(self):
        """Should not create MetaTrader 4 demo account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountGeneratorClient(http_client, domain_client)
        try:
            await account_client.create_mt4_demo_account({}, '')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke create_mt4_demo_account method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_demo_mt5(self):
        """Should create new MetaTrader 5 demo account."""
        with patch('lib.clients.metaapi.metatrader_account_generator_client.random_id', return_value='transactionId'):
            expected = {
                'login': '12345',
                'password': 'qwerty',
                'serverName': 'HugosWay-Demo3',
                'investorPassword': 'qwerty',
            }
            account = {
                'accountType': 'type',
                'balance': 10,
                'email': 'test@test.com',
                'leverage': 15,
                'serverName': 'server',
            }
            rsps = respx.post(
                f'{PROVISIONING_API_URL}/users/current/provisioning-profiles/profileId2/mt5-demo-accounts'
            ).mock(return_value=Response(200, json=expected))
            accounts = await demo_account_client.create_mt5_demo_account(account, 'profileId2')
            assert (
                rsps.calls[0].request.url
                == f'{PROVISIONING_API_URL}/users/current/provisioning-profiles/' + 'profileId2/mt5-demo-accounts'
            )
            assert rsps.calls[0].request.method == 'POST'
            assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
            assert rsps.calls[0].request.headers['transaction-id'] == 'transactionId'
            assert accounts == expected

    @pytest.mark.asyncio
    async def test_not_create_mt5_demo_with_account_token(self):
        """Should not create MetaTrader 5 demo account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountGeneratorClient(http_client, domain_client)
        try:
            await account_client.create_mt5_demo_account({}, '')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke create_mt5_demo_account method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )
