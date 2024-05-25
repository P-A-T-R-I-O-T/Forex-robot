import asyncio
from datetime import datetime

import pytest
from mock import MagicMock, AsyncMock, patch

from .connection_registry import ConnectionRegistry
from .memory_history_storage_model import MemoryHistoryStorageModel
from .models import MetatraderDeal
from .streaming_metaapi_connection import StreamingMetaApiConnection
from .. import SynchronizationListener
from ..clients.metaapi.metaapi_websocket_client import MetaApiWebsocketClient
from ..clients.metaapi.reconnect_listener import ReconnectListener
from ..metaapi.metatrader_account import MetatraderAccount
from ..metaapi.models import MetatraderOrder


class MockClient(MetaApiWebsocketClient):
    def add_synchronization_listener(self, account_id: str, listener):
        pass

    def add_reconnect_listener(self, listener: ReconnectListener, account_id: str):
        pass

    def remove_synchronization_listener(self, account_id: str, listener: SynchronizationListener):
        pass

    def remove_account_cache(self, account_id: str):
        pass

    def remove_reconnect_listener(self, listener: ReconnectListener):
        pass

    async def subscribe(self, account_id: str, instance_index: str = None):
        pass

    async def unsubscribe(self, account_id: str):
        pass

    def add_account_cache(self, account_id: str, replicas: dict):
        pass

    def ensure_subscribe(self, account_id: str, instance_number: int):
        pass


class MockStorage(MemoryHistoryStorageModel):
    def __init__(self):
        super().__init__()
        self._deals = []
        self._historyOrders = []

    @property
    def deals(self):
        return self._deals

    @property
    def history_orders(self):
        return self._historyOrders

    @property
    def last_deal_time_by_instance_index(self):
        return {}

    @property
    def last_history_order_time_by_instance_index(self):
        return {}

    async def clear(self):
        pass

    def last_deal_time(self, instance_index: str = None) -> datetime:
        pass

    def last_history_order_time(self, instance_index: str = None) -> datetime:
        pass

    def on_deal_added(self, instance_index: str, deal: MetatraderDeal):
        pass

    async def load_data_from_disk(self):
        return {'deals': [], 'history_orders': []}

    def on_history_order_added(self, instance_index: str, history_order: MetatraderOrder):
        pass


mock_client: MockClient = None
mock_storage: MockStorage = None
registry: ConnectionRegistry = None


class MockAccount(MetatraderAccount):
    def __init__(self, id: str):
        super().__init__(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), '')
        self._id = id

    @property
    def id(self):
        return self._id

    @property
    def account_regions(self) -> dict:
        return {'vint-hill': 'id', 'new-york': 'idReplica'}


def create_connection_mock():
    mock = StreamingMetaApiConnection(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), registry)
    mock.initialize = AsyncMock()
    mock.subscribe = AsyncMock()
    return mock


@pytest.fixture(autouse=True)
async def run_around_tests():
    global mock_client
    mock_client = MockClient(MagicMock(), MagicMock(), 'token')
    global mock_storage
    mock_storage = MagicMock()
    global registry
    registry = ConnectionRegistry({}, mock_client, MagicMock())
    yield


class TestConnectionRegistry:
    @pytest.mark.asyncio
    async def test_create_streaming(self):
        """Should create streaming connection."""
        with patch('lib.metaapi.connection_registry.StreamingMetaApiConnection') as mock_connection:
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            connection = registry.connect_streaming(account, mock_storage)
            await connection.connect()
            assert connection.history_storage == connection_instance.history_storage
            assert 'id' in registry._streaming_connections

    @pytest.mark.asyncio
    async def test_disconnect_streaming(self):
        """Should disconnect streaming connection."""
        with patch('lib.metaapi.connection_registry.StreamingMetaApiConnection') as mock_connection:
            mock_client.unsubscribe = AsyncMock()
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            registry.connect_streaming(account, mock_storage)
            await registry.remove_streaming(account)
            mock_client.unsubscribe.assert_any_call('id')
            mock_client.unsubscribe.assert_any_call('idReplica')

    @pytest.mark.asyncio
    async def test_not_disconnect_until_both_are_closed_1(self):
        """Should not disconnect until both streaming and rpc connections are closed."""
        with patch('lib.metaapi.connection_registry.StreamingMetaApiConnection') as mock_connection:
            mock_client.unsubscribe = AsyncMock()
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            registry.connect_streaming(account, mock_storage)
            registry.connect_streaming(account, mock_storage)
            registry.connect_rpc(account)
            await registry.remove_streaming(account)
            mock_client.unsubscribe.assert_not_called()
            await registry.remove_streaming(account)
            mock_client.unsubscribe.assert_not_called()
            await registry.remove_rpc(account)
            mock_client.unsubscribe.assert_any_call('id')
            mock_client.unsubscribe.assert_any_call('idReplica')

    @pytest.mark.asyncio
    async def test_create_rpc_connection(self):
        """Should create rpc connection."""
        with patch('lib.metaapi.connection_registry.RpcMetaApiConnection') as mock_connection:
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            connection = registry.connect_rpc(account)
            await connection.connect()
            assert 'id' in registry._rpc_connections

    @pytest.mark.asyncio
    async def test_disconnect_rpc_connection(self):
        """Should disconnect rpc connection."""
        with patch('lib.metaapi.connection_registry.RpcMetaApiConnection') as mock_connection:
            mock_client.unsubscribe = AsyncMock()
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            registry.connect_rpc(account)
            await registry.remove_rpc(account)
            mock_client.unsubscribe.assert_any_call('id')
            mock_client.unsubscribe.assert_any_call('idReplica')

    @pytest.mark.asyncio
    async def test_not_disconnect_until_both_are_closed_2(self):
        """Should not disconnect until both rpc and streaming connections are closed."""
        with patch('lib.metaapi.connection_registry.StreamingMetaApiConnection') as mock_connection:
            mock_client.unsubscribe = AsyncMock()
            connection_instance = create_connection_mock()
            mock_connection.return_value = connection_instance
            account = MockAccount('id')
            registry.connect_rpc(account)
            registry.connect_rpc(account)
            registry.connect_streaming(account, mock_storage)
            await registry.remove_rpc(account)
            mock_client.unsubscribe.assert_not_called()
            await registry.remove_rpc(account)
            mock_client.unsubscribe.assert_not_called()
            await registry.remove_streaming(account)
            mock_client.unsubscribe.assert_any_call('id')
            mock_client.unsubscribe.assert_any_call('idReplica')

    @pytest.mark.asyncio
    async def test_close_connection_instances(self):
        """Should close connection instances."""
        account = MockAccount('id')
        rpc_1 = registry.connect_rpc(account)
        rpc_2 = registry.connect_rpc(account)
        rpc_3 = registry.connect_rpc(account)
        streaming_1 = registry.connect_streaming(account, AsyncMock())
        streaming_2 = registry.connect_streaming(account, AsyncMock())
        streaming_3 = registry.connect_streaming(account, AsyncMock())
        await rpc_1.connect()
        await streaming_1.connect()
        rpc_1.close = AsyncMock(wraps=rpc_1.close)
        rpc_2.close = AsyncMock(wraps=rpc_2.close)
        rpc_3.close = AsyncMock(wraps=rpc_3.close)
        streaming_1.close = AsyncMock(wraps=streaming_1.close)
        streaming_2.close = AsyncMock(wraps=streaming_2.close)
        streaming_3.close = AsyncMock(wraps=streaming_3.close)

        assert len(registry.streaming_connections) == 1
        assert len(registry.rpc_connections) == 1

        registry.close_all_instances('id')
        await asyncio.sleep(1)

        rpc_1.close.assert_called_once()
        rpc_2.close.assert_called_once()
        rpc_3.close.assert_called_once()
        streaming_1.close.assert_called_once()
        streaming_2.close.assert_called_once()
        streaming_3.close.assert_called_once()
        assert len(registry.streaming_connections) == 0
        assert len(registry.rpc_connections) == 0
