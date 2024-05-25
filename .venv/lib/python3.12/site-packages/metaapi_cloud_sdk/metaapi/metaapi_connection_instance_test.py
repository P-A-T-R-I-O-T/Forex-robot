from unittest.mock import MagicMock

import pytest
from mock.mock import AsyncMock

from lib.clients.metaapi.metaapi_websocket_client import MetaApiWebsocketClient
from lib.metaapi.metaapi_connection import MetaApiConnection
from lib.metaapi.metaapi_connection_instance import MetaApiConnectionInstance
from lib.metaapi.metatrader_account import MetatraderAccount

websocket_client: MetaApiWebsocketClient = None
connection_instance: MetaApiConnectionInstance = None


class MockAccount(MetatraderAccount):
    def __init__(self, id):
        super().__init__(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), 'MetaApi')
        self._id = id

    @property
    def id(self):
        return self._id


class MockConnection(MetaApiConnection):
    async def connect(self, instance_id: str):
        pass

    async def close(self, instance_id: str):
        pass

    def __init__(self):
        super().__init__(MagicMock(), MagicMock(), MockAccount('accountId'), 'MetaApi')


@pytest.fixture(autouse=True)
async def run_around_tests():
    connection: MetaApiConnection = MockConnection()

    global websocket_client
    websocket_client = MagicMock()
    global connection_instance
    connection_instance = MetaApiConnectionInstance(websocket_client, connection)
    await connection_instance.connect()


class TestRefreshSymbolQuotes:
    @pytest.mark.asyncio
    async def test_refresh_symbol_quotes(self):
        """Should refresh symbol quotes."""
        websocket_client.refresh_symbol_quotes = AsyncMock(
            return_value={'quotes': [{'symbol': 'EURUSD'}, {'symbol': 'BTCUSD'}], 'balance': 1100}
        )
        assert await connection_instance.refresh_symbol_quotes(['EURUSD', 'BTCUSD']) == {
            'quotes': [{'symbol': 'EURUSD'}, {'symbol': 'BTCUSD'}],
            'balance': 1100,
        }
        websocket_client.refresh_symbol_quotes.assert_called_with('accountId', ['EURUSD', 'BTCUSD'])
