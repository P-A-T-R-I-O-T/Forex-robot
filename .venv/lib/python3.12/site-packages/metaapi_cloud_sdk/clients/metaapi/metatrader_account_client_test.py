import json

import pytest
import respx
from httpx import Response
from mock import MagicMock, AsyncMock, patch

from .metatrader_account_client import MetatraderAccountClient
from ..http_client import HttpClient

PROVISIONING_API_URL = 'https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai'
http_client = HttpClient()
token = 'header.payload.sign'
account_token = 'token'
domain_client: MagicMock = None
account_client: MetatraderAccountClient = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    global http_client
    http_client = HttpClient()
    global domain_client
    domain_client = MagicMock()
    domain_client.token = token
    domain_client.domain = 'agiliumtrade.agiliumtrade.ai'
    domain_client.get_url = AsyncMock(return_value=PROVISIONING_API_URL)
    global account_client
    account_client = MetatraderAccountClient(http_client, domain_client)


class TestMetatraderAccountClient:
    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_many(self):
        """Should retrieve MetaTrader accounts from API."""
        expected = [
            {
                '_id': '1eda642a-a9a3-457c-99af-3bc5e8d5c4c9',
                'login': '50194988',
                'name': 'mt5a',
                'server': 'ICMarketsSC-Demo',
                'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                'magic': 123456,
                'connectionStatus': 'DISCONNECTED',
                'state': 'DEPLOYED',
                'type': 'cloud',
                'tags': ['tag1', 'tag2'],
            }
        ]
        rsps = respx.get(f'{PROVISIONING_API_URL}/users/current/accounts').mock(
            return_value=Response(200, json=expected)
        )
        accounts = await account_client.get_accounts({'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076'})
        assert (
            rsps.calls[0].request.url
            == f'{PROVISIONING_API_URL}/users/current/accounts'
            + '?provisioningProfileId=f9ce1f12-e720-4b9a-9477-c2d4cb25f076'
        )
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert accounts == expected

    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_metatrader_accounts_from_api_using_exact_api_version(self):
        """Should retrieve MetaTrader accounts from API using exact api version."""
        expected = [
            {
                '_id': '1eda642a-a9a3-457c-99af-3bc5e8d5c4c9',
                'login': '50194988',
                'name': 'mt5a',
                'server': 'ICMarketsSC-Demo',
                'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                'magic': 123456,
                'application': 'MetaApi',
                'connectionStatus': 'DISCONNECTED',
                'state': 'DEPLOYED',
                'type': 'cloud',
                'tags': ['tag1', 'tag2'],
            }
        ]
        api_version = '1'
        rsps = respx.get(f'{PROVISIONING_API_URL}/users/current/accounts').mock(
            return_value=Response(200, json=expected)
        )
        accounts = await account_client.get_accounts(
            {'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076'}, api_version
        )
        assert (
            rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts'
            '?provisioningProfileId=f9ce1f12-e720-4b9a-9477-c2d4cb25f076'
        )
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert rsps.calls[0].request.headers['api-version'] == '1'
        assert accounts == expected

    @pytest.mark.asyncio
    async def test_not_retrieve_mt_accounts_with_account_token(self):
        """Should not retrieve MetaTrader accounts from API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.get_accounts({'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076'})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke get_accounts method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_one(self):
        """Should retrieve MetaTrader account from API."""
        expected = {
            '_id': 'id',
            'login': '50194988',
            'name': 'mt5a',
            'server': 'ICMarketsSC-Demo',
            'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
            'magic': 123456,
            'connectionStatus': 'DISCONNECTED',
            'state': 'DEPLOYED',
            'type': 'cloud',
            'tags': ['tag1', 'tag2'],
        }
        rsps = respx.get(f'{PROVISIONING_API_URL}/users/current/accounts/id').mock(
            return_value=Response(200, json=expected)
        )
        accounts = await account_client.get_account('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id'
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert accounts == expected

    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_replica(self):
        """Should retrieve MetaTrader account replica from API."""
        expected = {
            '_id': 'id',
            'login': '50194988',
            'name': 'mt5a',
            'server': 'ICMarketsSC-Demo',
            'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
            'magic': 123456,
            'connectionStatus': 'DISCONNECTED',
            'state': 'DEPLOYED',
            'type': 'cloud',
            'tags': ['tag1', 'tag2'],
        }
        rsps = respx.get(f'{PROVISIONING_API_URL}/users/current/accounts/id/replicas/idReplica').mock(
            return_value=Response(200, json=expected)
        )
        replica = await account_client.get_account_replica('id', 'idReplica')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/replicas/idReplica'
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert replica == expected

    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieve_replicas(self):
        """Should retrieve MetaTrader account replicas from API."""
        expected = [
            {
                '_id': 'idReplica',
                'login': '50194988',
                'name': 'mt5a',
                'server': 'ICMarketsSC-Demo',
                'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                'magic': 123456,
                'application': 'MetaApi',
                'connectionStatus': 'DISCONNECTED',
                'state': 'DEPLOYED',
                'type': 'cloud',
                'tags': ['tag1', 'tag2'],
            },
            {
                '_id': 'idReplica2',
                'login': '50194988',
                'name': 'mt5a',
                'server': 'ICMarketsSC-Demo',
                'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                'magic': 123456,
                'application': 'MetaApi',
                'connectionStatus': 'DISCONNECTED',
                'state': 'DEPLOYED',
                'type': 'cloud',
                'tags': ['tag1', 'tag2'],
            },
        ]
        rsps = respx.get(f'{PROVISIONING_API_URL}/users/current/accounts/id/replicas').mock(
            return_value=Response(200, json=expected)
        )
        replicas = await account_client.get_account_replicas('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/replicas'
        assert rsps.calls[0].request.method == 'GET'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert replicas == expected

    @respx.mock
    @pytest.mark.asyncio
    async def test_create(self):
        """Should create MetaTrader account via API."""
        with patch('lib.clients.metaapi.metatrader_account_client.random_id', return_value='transactionId'):
            expected = {'id': 'id'}
            account = {
                'login': '50194988',
                'password': 'Test1234',
                'name': 'mt5a',
                'server': 'ICMarketsSC-Demo',
                'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                'magic': 123456,
                'type': 'cloud',
                'tags': ['tag1'],
            }
            rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts').mock(
                return_value=Response(201, json=expected)
            )
            accounts = await account_client.create_account(account)
            assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts'
            assert rsps.calls[0].request.method == 'POST'
            assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
            assert rsps.calls[0].request.headers['transaction-id'] == 'transactionId'
            assert accounts == expected

    @pytest.mark.asyncio
    async def test_not_create_mt_account_with_account_token(self):
        """Should not create MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.create_account({})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke create_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_replica(self):
        """Should create MetaTrader account replica via API."""
        with patch('lib.clients.metaapi.metatrader_account_client.random_id', return_value='transactionId'):
            expected = {'id': 'id'}
            replica = {'magic': 123456, 'symbol': 'EURUSD'}
            rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas').mock(
                return_value=Response(201, json=expected)
            )
            accounts = await account_client.create_account_replica('accountId', replica)
            assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas'
            assert rsps.calls[0].request.method == 'POST'
            assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
            assert rsps.calls[0].request.headers['transaction-id'] == 'transactionId'
            assert accounts == expected

    @pytest.mark.asyncio
    async def test_not_create_mt_account_replica_with_account_token(self):
        """Should not create MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.create_account_replica('accountId', {})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke create_account_replica method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_deploy(self):
        """Should deploy MetaTrader account via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/deploy').mock(return_value=Response(204))
        await account_client.deploy_account('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/deploy'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_deploy_mt_account_with_account_token(self):
        """Should not deploy MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.deploy_account('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke deploy_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_deploy_replica(self):
        """Should deploy MetaTrader account replica via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id/deploy').mock(
            return_value=Response(204)
        )
        await account_client.deploy_account_replica('accountId', 'id')
        assert (
            rsps.calls[0].request.url
            == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/' + 'id/deploy'
        )
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_deploy_mt_account_replica_with_account_token(self):
        """Should not deploy MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.deploy_account_replica('accountId', 'id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke deploy_account_replica method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_undeploy(self):
        """Should undeploy MetaTrader account via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/undeploy').mock(return_value=Response(204))
        await account_client.undeploy_account('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/undeploy'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_undeploy_mt_account_with_account_token(self):
        """Should not undeploy MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.undeploy_account('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke undeploy_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_undeploy_replica(self):
        """Should undeploy MetaTrader account replica via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id/undeploy').mock(
            return_value=Response(204)
        )
        await account_client.undeploy_account_replica('accountId', 'id')
        assert (
            rsps.calls[0].request.url
            == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas' + '/id/undeploy'
        )
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_undeploy_mt_account_replica_with_account_token(self):
        """Should not undeploy MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.undeploy_account('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke undeploy_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_redeploy(self):
        """Should redeploy MetaTrader account via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/redeploy').mock(return_value=Response(204))
        await account_client.redeploy_account('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/redeploy'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_redeploy_mt_account_with_account_token(self):
        """Should not redeploy MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.redeploy_account('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke redeploy_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_redeploy_replica(self):
        """Should redeploy MetaTrader account replica via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id/redeploy').mock(
            return_value=Response(204)
        )
        await account_client.redeploy_account_replica('accountId', 'id')
        assert (
            rsps.calls[0].request.url
            == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas' + '/id/redeploy'
        )
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_redeploy_mt_account_replica_with_account_token(self):
        """Should not redeploy MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.redeploy_account_replica('accountId', 'id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke redeploy_account_replica method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete(self):
        """Should delete MetaTrader account via API."""
        rsps = respx.delete(f'{PROVISIONING_API_URL}/users/current/accounts/id').mock(return_value=Response(204))
        await account_client.delete_account('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id'
        assert rsps.calls[0].request.method == 'DELETE'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_delete_mt_account_with_account_token(self):
        """Should not delete MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.delete_account('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke delete_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_replica(self):
        """Should delete MetaTrader account replica via API."""
        rsps = respx.delete(f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id').mock(
            return_value=Response(204)
        )
        await account_client.delete_account_replica('accountId', 'id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id'
        assert rsps.calls[0].request.method == 'DELETE'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_delete_mt_account_replica_with_account_token(self):
        """Should not delete MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.delete_account_replica('accountId', 'id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke delete_account_replica method, because you have connected '
                + 'with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_update(self):
        """Should update MetaTrader account via API."""
        update_account = {
            'name': 'new account name',
            'password': 'new_password007',
            'server': 'ICMarketsSC2-Demo',
            'tags': ['tag1'],
        }
        rsps = respx.put(f'{PROVISIONING_API_URL}/users/current/accounts/id', json=update_account).mock(
            return_value=Response(204)
        )
        await account_client.update_account('id', update_account)
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id'
        assert rsps.calls[0].request.method == 'PUT'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert rsps.calls[0].request.content == json.dumps(update_account).encode('utf-8')

    @pytest.mark.asyncio
    async def test_not_update_mt_account_with_account_token(self):
        """Should not update MetaTrader account via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.update_account('id', {})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke update_account method, because you have connected with '
                + 'account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_replica(self):
        """Should update MetaTrader account replica via API."""
        update_account_replica = {'magic': 0, 'tags': ['tag1']}
        rsps = respx.put(
            f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id', json=update_account_replica
        ).mock(return_value=Response(204))
        await account_client.update_account_replica('accountId', 'id', update_account_replica)
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/accountId/replicas/id'
        assert rsps.calls[0].request.method == 'PUT'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'
        assert rsps.calls[0].request.content == json.dumps(update_account_replica).encode('utf-8')

    @pytest.mark.asyncio
    async def test_not_update_mt_account_replica_with_account_token(self):
        """Should not update MetaTrader account replica via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.update_account_replica('accountId', 'id', {})
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke update_account_replica method, because you have '
                + 'connected with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_increase_reliability(self):
        """Should increase MetaTrader account reliability via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/increase-reliability').mock(
            return_value=Response(204)
        )
        await account_client.increase_reliability('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/increase-reliability'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_increase_reliability_with_account_token(self):
        """Should not increase MetaTrader account reliability via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.increase_reliability('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__()
                == 'You can not invoke increase_reliability method, because you have connected '
                + 'with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_enable_risk_management_api_via_api(self):
        """Should enable risk management API via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/enable-risk-management-api').mock(
            return_value=Response(204)
        )
        await account_client.enable_risk_management_api('id')
        assert (
            rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/enable-risk-management-api'
        )
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_enable_risk_management_api_via_api_with_account_token(self):
        """Should not enable risk management API via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.enable_risk_management_api('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__() == 'You can not invoke enable_risk_management_api method, '
                'because you have connected '
                + 'with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_enable_metastats_api_via_api(self):
        """Should enable MetaStats API via API."""
        rsps = respx.post(f'{PROVISIONING_API_URL}/users/current/accounts/id/enable-metastats-api').mock(
            return_value=Response(204)
        )
        await account_client.enable_metastats_api('id')
        assert rsps.calls[0].request.url == f'{PROVISIONING_API_URL}/users/current/accounts/id/enable-metastats-api'
        assert rsps.calls[0].request.method == 'POST'
        assert rsps.calls[0].request.headers['auth-token'] == 'header.payload.sign'

    @pytest.mark.asyncio
    async def test_not_enable_metastats_api_via_api_with_account_token(self):
        """Should not enable MetaStats api via API with account token."""
        domain_client.token = account_token
        account_client = MetatraderAccountClient(http_client, domain_client)
        try:
            await account_client.enable_metastats_api('id')
            pytest.fail()
        except Exception as err:
            assert (
                err.__str__() == 'You can not invoke enable_metastats_api method, '
                'because you have connected '
                + 'with account access token. Please use API access token from '
                + 'https://app.metaapi.cloud/api-access/generate-token page to invoke this method.'
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_configuration_link_via_api(self):
        """Should generate a configuration link via API."""
        rsps = respx.put(f'{PROVISIONING_API_URL}/users/current/accounts/id/configuration-link').mock(
            return_value=Response(204)
        )
        await account_client.create_configuration_link('id', 14)
        assert (
            rsps.calls[0].request.url
            == f'{PROVISIONING_API_URL}/users/current/accounts/id/configuration-link?ttlInDays=14'
        )
        assert rsps.calls[0].request.method == 'PUT'
        assert rsps.calls[0].request.headers['auth-token'] == token
