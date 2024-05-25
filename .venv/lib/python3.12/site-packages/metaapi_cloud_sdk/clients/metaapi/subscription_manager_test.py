import asyncio
from asyncio import sleep
from datetime import datetime, timedelta

import pytest
from mock import MagicMock, AsyncMock, patch

from .metaapi_websocket_client import MetaApiWebsocketClient
from .subscription_manager import SubscriptionManager
from ..error_handler import TooManyRequestsException, NotFoundException
from ..timeout_exception import TimeoutException
from ... import MetaApi
from ...metaapi.models import format_date


class MockClient(MetaApiWebsocketClient):
    def subscribe(self, account_id: str, instance_index: str = None):
        pass


client: MockClient = None
manager: SubscriptionManager = None
meta_api: MetaApi = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch('lib.clients.metaapi.subscription_manager.uniform', new=MagicMock(return_value=1)):
        global meta_api
        meta_api = MetaApi(MagicMock())
        meta_api._connection_registry._rpc_connections = {'accountId1': MagicMock()}
        meta_api._connection_registry._streaming_connections = {'accountId1': MagicMock()}
        global client
        client = MockClient(meta_api, MagicMock(), 'token')
        client._socket_instances = {'vint-hill': {0: [{'socket': MagicMock()}, {'socket': MagicMock()}]}}
        client._socket_instances['vint-hill'][0][0]['socket'].connected = True
        client._socket_instances['vint-hill'][0][1]['socket'].connected = False
        client.get_account_region = MagicMock(return_value='vint-hill')
        client._socket_instances_by_accounts = {0: {'accountId': 0}}
        client._accounts_by_replica_id = {'accountId': 'accountId1'}
        client._latency_service.get_active_account_instances = MagicMock()
        global manager
        manager = SubscriptionManager(client, meta_api)
        yield


@pytest.fixture
def client_rpc_request_stub():
    stub = AsyncMock()
    client.rpc_request = stub

    return stub


@pytest.fixture
def rpc_connection_refresh_stub():
    stub = MagicMock()
    meta_api._connection_registry.rpc_connections['accountId1'].schedule_refresh = stub

    return stub


@pytest.fixture
def streaming_connection_refresh_stub():
    stub = MagicMock()
    meta_api._connection_registry.streaming_connections['accountId1'].schedule_refresh = stub

    return stub


@pytest.fixture
def latency_service_get_active_account_instances_stub():
    stub = MagicMock()
    client._latency_service.get_active_account_instances = stub

    return stub


class TestSubscriptionManager:
    @pytest.mark.asyncio
    async def test_subscribe_to_terminal(self, client_rpc_request_stub):
        """Should subscribe to terminal."""
        client.subscribe = AsyncMock()

        async def delay_connect():
            await sleep(0.1)
            await manager.cancel_subscribe('accountId:0')

        asyncio.create_task(delay_connect())
        await manager.schedule_subscribe('accountId', 0)
        client_rpc_request_stub.assert_called_with('accountId', {'type': 'subscribe', 'instanceIndex': 0})

    @pytest.mark.asyncio
    async def test_retry_subscribe(self, client_rpc_request_stub):
        """Should retry subscribe if no response received."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            response = {'type': 'response', 'accountId': 'accountId', 'requestId': 'requestId'}
            client_rpc_request_stub.side_effect = [TimeoutException('timeout'), response, response]

            async def delay_connect():
                await sleep(0.36)
                await manager.cancel_subscribe('accountId:0')

            asyncio.create_task(delay_connect())
            await manager.schedule_subscribe('accountId', 0)
            client_rpc_request_stub.assert_called_with('accountId', {'type': 'subscribe', 'instanceIndex': 0})
            assert client_rpc_request_stub.call_count == 2

    @pytest.mark.asyncio
    async def test_wait_on_too_many_requests_error(self, client_rpc_request_stub):
        """Should wait for recommended time if too many requests error received."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            response = {'type': 'response', 'accountId': 'accountId', 'requestId': 'requestId'}
            client_rpc_request_stub.side_effect = [
                TooManyRequestsException(
                    'timeout',
                    {
                        'periodInMinutes': 60,
                        'maxRequestsForPeriod': 10000,
                        "type": "LIMIT_REQUEST_RATE_PER_USER",
                        'recommendedRetryTime': format_date(datetime.now() + timedelta(seconds=5)),
                    },
                ),
                response,
                response,
            ]

            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            await sleep(0.36)
            assert client_rpc_request_stub.call_count == 1
            await sleep(0.2)
            manager.cancel_subscribe('accountId:0')
            client_rpc_request_stub.assert_called_with('accountId', {'type': 'subscribe', 'instanceIndex': 0})
            assert client_rpc_request_stub.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_on_reconnect(self, client_rpc_request_stub):
        """Should cancel all subscriptions on reconnect."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            client.connect = AsyncMock()
            client._socket_instances_by_accounts[0] = {'accountId': 0, 'accountId2': 0, 'accountId3': 1}
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId2', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId3', 0))
            await sleep(0.1)
            manager.on_reconnected(0, 0, [])
            await sleep(0.5)
            assert client_rpc_request_stub.call_count == 4

    @pytest.mark.asyncio
    async def test_restart_on_reconnect(self, client_rpc_request_stub):
        """Should restart subscriptions on reconnect."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            client.connect = AsyncMock()
            client._socket_instances_by_accounts[0] = {'accountId': 0, 'accountId2': 0, 'accountId3': 0}
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId2', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId3', 0))
            await sleep(0.1)
            manager.on_reconnected(0, 0, ['accountId', 'accountId2'])
            await sleep(0.2)
            assert client_rpc_request_stub.call_count == 5

    @pytest.mark.asyncio
    async def test_wait_for_stop_on_reconnect(self, client_rpc_request_stub):
        """Should wait until previous subscription ends on reconnect."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):

            async def delay_subscribe(account_id: str, instance_number: int = None):
                await sleep(0.2)

            client.connect = AsyncMock()
            client._socket_instances_by_accounts[0] = {'accountId': 0}
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            await sleep(0.1)
            manager.on_reconnected(0, 0, ['accountId'])
            await sleep(0.3)
            assert client_rpc_request_stub.call_count == 2

    @pytest.mark.asyncio
    async def test_no_multiple_subscribes(self, client_rpc_request_stub):
        """Should not send multiple subscribe requests at the same time."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            await sleep(0.1)
            manager.cancel_subscribe('accountId:0')
            await sleep(0.25)
            client_rpc_request_stub.assert_called_with('accountId', {'type': 'subscribe', 'instanceIndex': 0})
            assert client_rpc_request_stub.call_count == 1

    @pytest.mark.asyncio
    async def test_resubscribe_on_timeout(self, client_rpc_request_stub):
        """Should resubscribe on timeout."""
        client._socket_instances['vint-hill'][0][0]['socket'].connected = True
        client._socket_instances_by_accounts[0]['accountId2'] = 1
        client._regions_by_accounts = {'accountId': {'region': 'vint-hill'}, 'accountId2': {'region': 'vint-hill'}}

        async def delay_connect():
            await sleep(0.1)
            await manager.cancel_subscribe('accountId:0')
            await manager.cancel_subscribe('accountId2:0')

        asyncio.create_task(delay_connect())
        manager.on_timeout('accountId', 0)
        manager.on_timeout('accountId2', 0)
        await sleep(0.2)
        client_rpc_request_stub.assert_called_with('accountId', {'type': 'subscribe', 'instanceIndex': 0})
        assert client_rpc_request_stub.call_count == 1

    @pytest.mark.asyncio
    async def test_not_subscribe_if_disconnected(self, client_rpc_request_stub):
        """Should not retry subscribe to terminal if connection is closed."""
        client._socket_instances['vint-hill'][0][0]['socket'].connected = False

        async def delay_connect():
            await sleep(0.1)
            await manager.cancel_subscribe('accountId:0')

        asyncio.create_task(delay_connect())
        manager.on_timeout('accountId', 0)
        await sleep(0.05)
        client_rpc_request_stub.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_account(self, client_rpc_request_stub):
        """Should cancel all subscriptions for an account."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 10)):
            asyncio.create_task(manager.schedule_subscribe('accountId', 0))
            asyncio.create_task(manager.schedule_subscribe('accountId', 1))
            await sleep(0.1)
            manager.cancel_account('accountId')
            await sleep(0.5)
            assert client_rpc_request_stub.call_count == 2

    @pytest.mark.asyncio
    async def test_should_destroy_subscribe_process_on_cancel(self):
        """Should destroy subscribe process on cancel."""
        subscribe = AsyncMock()

        async def delay_subscribe(account_id, instance_index):
            await subscribe()
            await asyncio.sleep(0.4)
            return

        client.rpc_request = delay_subscribe
        asyncio.create_task(manager.schedule_subscribe('accountId', 0))
        await asyncio.sleep(0.05)
        manager.cancel_subscribe('accountId:0')
        await asyncio.sleep(0.05)
        asyncio.create_task(manager.schedule_subscribe('accountId', 0))
        await asyncio.sleep(0.05)
        assert subscribe.call_count == 2

    @pytest.mark.asyncio
    async def test_is_subscribing(self):
        """Should check if account is subscribing."""
        asyncio.create_task(manager.schedule_subscribe('accountId', 1))
        await asyncio.sleep(0.05)
        assert manager.is_account_subscribing('accountId')
        assert not manager.is_account_subscribing('accountId', 0)
        assert manager.is_account_subscribing('accountId', 1)

    @pytest.mark.asyncio
    async def test_refresh_account_on_not_found_exception(
        self, client_rpc_request_stub, rpc_connection_refresh_stub, streaming_connection_refresh_stub
    ):
        """Should refresh account on NotFoundException exception."""
        client_rpc_request_stub.side_effect = NotFoundException('test')
        asyncio.create_task(manager.schedule_subscribe('accountId', 1))
        await sleep(0.05)

        rpc_connection_refresh_stub.assert_called_with('vint-hill')
        streaming_connection_refresh_stub.assert_called_with('vint-hill')

    @pytest.mark.asyncio
    async def test_refresh_account_on_timeout_exception(
        self,
        client_rpc_request_stub,
        rpc_connection_refresh_stub,
        streaming_connection_refresh_stub,
        latency_service_get_active_account_instances_stub,
    ):
        """Should refresh account on TimeoutException exception."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 100)):
            client_rpc_request_stub.side_effect = TimeoutException('timeout')
            latency_service_get_active_account_instances_stub.return_value = ['accountId:vint-hill']
            asyncio.create_task(manager.schedule_subscribe('accountId', 1))
            await sleep(0.01)
            rpc_connection_refresh_stub.assert_not_called()
            streaming_connection_refresh_stub.assert_not_called()
            await sleep(0.6)
            rpc_connection_refresh_stub.assert_called_with('vint-hill')
            streaming_connection_refresh_stub.assert_called_with('vint-hill')

    @pytest.mark.asyncio
    async def test_not_call_timeout_if_connected_to_region(
        self,
        client_rpc_request_stub,
        rpc_connection_refresh_stub,
        streaming_connection_refresh_stub,
        latency_service_get_active_account_instances_stub,
    ):
        """Should not call timeout if connected to region."""
        with patch('lib.clients.metaapi.subscription_manager.asyncio.sleep', new=lambda x: sleep(x / 100)):
            client_rpc_request_stub.side_effect = TimeoutException('timeout')
            latency_service_get_active_account_instances_stub.return_value = ['accountId1:vint-hill']
            asyncio.create_task(manager.schedule_subscribe('accountId', 1))
            await sleep(0.01)
            rpc_connection_refresh_stub.assert_not_called()
            streaming_connection_refresh_stub.assert_not_called()
            await sleep(0.6)
            rpc_connection_refresh_stub.assert_not_called()
            streaming_connection_refresh_stub.assert_not_called()
