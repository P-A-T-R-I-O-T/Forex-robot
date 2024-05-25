import asyncio
import json
from asyncio import sleep, wait_for
from copy import deepcopy
from datetime import datetime, timedelta
from math import floor
from random import random

import pytest
from aiohttp import web
from freezegun import freeze_time
from mock import patch, AsyncMock
from mock.mock import MagicMock
from socketio import AsyncServer

from .. import MetaApi
from ..clients.error_handler import NotFoundException
from ..logger import LoggerManager
from ..metaapi.models import format_date, date, format_error

logger = LoggerManager.get_logger('test')

api: MetaApi = None
account_information = {
    "broker": "True ECN Trading Ltd",
    "currency": "USD",
    "server": "ICMarketsSC-Demo",
    "balance": 7319.9,
    "equity": 7306.649913200001,
    "margin": 184.1,
    "freeMargin": 7120.22,
    "leverage": 100,
    "marginLevel": 3967.58283542,
}
default_positions = [
    {
        'id': '46214692',
        'type': 'POSITION_TYPE_BUY',
        'symbol': 'GBPUSD',
        'magic': 1000,
        'time': '2020-04-15T02:45:06.521Z',
        'updateTime': '2020-04-15T02:45:06.521Z',
        'openPrice': 1,
        'currentPrice': 1.1,
        'currentTickValue': 1,
        'volume': 0.05,
        'swap': 0,
        'profit': -85.25999999999966,
        'commission': -0.25,
        'clientId': 'TE_GBPUSD_7hyINWqAlE',
        'stopLoss': 1.17721,
        'unrealizedProfit': -85.25999999999901,
        'realizedProfit': -6.536993168992922e-13,
    }
]
default_orders = [
    {
        'id': '46871284',
        'type': 'ORDER_TYPE_BUY_LIMIT',
        'state': 'ORDER_STATE_PLACED',
        'symbol': 'AUDNZD',
        'magic': 123456,
        'platform': 'mt5',
        'time': '2020-04-20T08:38:58.270Z',
        'openPrice': 1.03,
        'currentPrice': 1.05206,
        'volume': 0.05,
        'currentVolume': 0.01,
        'comment': 'COMMENT2',
    }
]
errors = [
    {
        "id": 1,
        "error": "TooManyRequestsError",
        "message": "One user can connect to one server no more than 300 accounts. Current number of connected "
        "accounts 300. For more information see https://metaapi.cloud/docs/client/rateLimiting/",
        "metadata": {
            "maxAccountsPerUserPerServer": 300,
            "accountsCount": 300,
            "recommendedRetryTime": format_date(datetime.now() + timedelta(seconds=20)),
            "type": "LIMIT_ACCOUNT_SUBSCRIPTIONS_PER_USER_PER_SERVER",
        },
    },
    {
        "id": 1,
        "error": "TooManyRequestsError",
        "message": "You have used all your account subscriptions quota. You have 50 account subscriptions available "
        "and have used 50 subscriptions. Please deploy more accounts to get more subscriptions. For more "
        "information see https://metaapi.cloud/docs/client/rateLimiting/",
        "metadata": {
            "maxAccountsPerUser": 50,
            "accountsCount": 50,
            "recommendedRetryTime": format_date(datetime.now() + timedelta(seconds=20)),
            "type": "LIMIT_ACCOUNT_SUBSCRIPTIONS_PER_USER",
        },
    },
    {
        "id": 1,
        "error": "TooManyRequestsError",
        "message": "You can not subscribe to more accounts on this connection because server is out of capacity. "
        "Please establish a new connection with a different client-id header value to switch to a "
        "different server. For more information see https://metaapi.cloud/docs/client/rateLimiting/",
        "metadata": {
            "changeClientIdHeader": True,
            "recommendedRetryTime": format_date(datetime.now() + timedelta(seconds=20)),
            "type": "LIMIT_ACCOUNT_SUBSCRIPTIONS_PER_SERVER",
        },
    },
]
default_specifications = [
    {'symbol': 'EURUSD', 'tickSize': 0.00001, 'minVolume': 0.01, 'maxVolume': 200, 'volumeStep': 0.01}
]
sync_host = 'ps-mpa-0'


class FakeServer:
    def __init__(self):
        self.app = web.Application()
        self.sio: AsyncServer = None
        self.runner = None
        self.stopped = False
        self.status_tasks = {}
        self._sequence_numbers = {}
        self.connections = []

    async def authenticate(self, data, sid, host=sync_host):
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "authenticated",
                    "accountId": data["accountId"],
                    "instanceIndex": 0,
                    "replicas": 1,
                    "host": host,
                },
                sid,
            )
        )

    async def emit_status(self, account_id: str, sid, host=sync_host):
        packet = {
            "connected": True,
            "authenticated": True,
            "instanceIndex": 0,
            "type": "status",
            "healthStatus": {"rpcApiHealthy": True},
            "replicas": 1,
            "host": host,
            "connectionId": account_id,
            "accountId": account_id,
        }
        asyncio.create_task(self.sio.emit("synchronization", packet, sid))

    async def create_status_task(self, account_id: str, sid, host=sync_host):
        while True:
            await self.emit_status(account_id, sid, host)
            await sleep(1)

    def delete_status_task(self, account_id: str):
        if account_id in self.status_tasks:
            self.status_tasks[account_id].cancel()
            del self.status_tasks[account_id]

    async def respond_account_information(self, data, sid):
        await self.sio.emit(
            "response",
            {
                "type": "response",
                "accountId": data["accountId"],
                "requestId": data["requestId"],
                "accountInformation": account_information,
            },
            sid,
        )

    def _use_sequence_number(self, sn_id: str):
        sequence_number = self._sequence_numbers.get(sn_id)
        if sequence_number is None:
            self._sequence_numbers[sn_id] = 1
        else:
            self._sequence_numbers[sn_id] += 1

        return sequence_number or 0

    async def sync_account(self, data, sid, host: str = None, opts: dict = None):
        if not host:
            host = sync_host
        if opts is None:
            opts = {}
        sn_id = data["accountId"] + ":0"
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "synchronizationStarted",
                    "accountId": data["accountId"],
                    "instanceIndex": 0,
                    "synchronizationId": data["requestId"],
                    "host": host,
                    "sequenceNumber": self._use_sequence_number(sn_id),
                    'specificationsHashIndex': opts.get('specificationsHashIndex'),
                    'positionsHashIndex': opts.get('positionsHashIndex'),
                    'ordersHashIndex': opts.get('ordersHashIndex'),
                },
                sid,
            )
        )
        await sleep(0.1)
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "accountInformation",
                    "accountId": data["accountId"],
                    "accountInformation": account_information,
                    "instanceIndex": 0,
                    "synchronizationId": data["requestId"],
                    "host": host,
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "specifications",
                    "accountId": data["accountId"],
                    "specifications": opts.get('specifications') or default_specifications,
                    "instanceIndex": 0,
                    "host": host,
                    "synchronizationId": data["requestId"],
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "positions",
                    "accountId": data["accountId"],
                    "positions": data.get('positions') or default_positions,
                    "instanceIndex": 0,
                    "host": host,
                    "synchronizationId": data["requestId"],
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "orders",
                    "accountId": data["accountId"],
                    "orders": data.get('orders') or default_orders,
                    "instanceIndex": 0,
                    "host": host,
                    "synchronizationId": data["requestId"],
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "orderSynchronizationFinished",
                    "accountId": data["accountId"],
                    "instanceIndex": 0,
                    "synchronizationId": data["requestId"],
                    "host": host,
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )
        await sleep(0.1)
        asyncio.create_task(
            self.sio.emit(
                "synchronization",
                {
                    "type": "dealSynchronizationFinished",
                    "accountId": data["accountId"],
                    "instanceIndex": 0,
                    "synchronizationId": data["requestId"],
                    "host": host,
                    "sequenceNumber": self._use_sequence_number(sn_id),
                },
                sid,
            )
        )

    async def respond(self, data, sid):
        await self.sio.emit(
            "response", {"type": "response", "accountId": data["accountId"], "requestId": data["requestId"]}, sid
        )

    async def emit_error(self, data, error_index, retry_after_seconds):
        error = errors[error_index]
        error["metadata"]["recommendedRetryTime"] = format_date(datetime.now() + timedelta(seconds=retry_after_seconds))
        await self.sio.emit("processingError", {**error, "requestId": data["requestId"]})

    def enable_sync(self):
        @self.sio.on("request")
        async def on_request(sid, data):
            if data["instanceIndex"] == 1:
                if data["type"] != "unsubscribe":
                    await self.respond(data, sid)
                    return
            if data["type"] == "subscribe":
                logger.debug(f"{sid}: subscribe request called {json.dumps(data)}")
                await sleep(0.2)
                await self.respond(data, sid)
                self.status_tasks[data["accountId"]] = asyncio.create_task(
                    self.create_status_task(data["accountId"], sid)
                )
                await self.authenticate(data, sid)
            elif data["type"] == "synchronize":
                await self.respond(data, sid)
                await self.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions", "unsubscribeFromMarketData"]:
                await self.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await self.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                self.delete_status_task(data["accountId"])
                await self.respond(data, sid)

    def disable_sync(self):
        @self.sio.on("request")
        async def on_request(sid, data):
            return False

    async def start(self, port=8080):
        global sio
        sio = AsyncServer(async_mode="aiohttp")
        self.sio = sio

        @self.sio.event
        async def connect(sid, environ):
            self.connections.append(sid)

        self.enable_sync()
        sio.attach(self.app, socketio_path="ws")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "localhost", port)
        await site.start()

    async def stop(self):
        if not self.stopped:
            self.stopped = True
            api.close()
            await self.runner.cleanup()

    async def close(self):
        for connection in self.connections:
            await self.sio.disconnect(connection)


fake_server: FakeServer = None


@pytest.fixture(autouse=True, params=[True])
async def run_around_tests(request):
    global sync_host
    sync_host = 'ps-mpa-0'
    global default_specifications
    default_specifications = [
        {'symbol': 'EURUSD', 'tickSize': 0.00001, 'minVolume': 0.01, 'maxVolume': 200, 'volumeStep': 0.01}
    ]
    global fake_server
    fake_server = FakeServer()
    await fake_server.start()
    global api
    api = MetaApi(
        "token",
        {
            "application": "application",
            "domain": "agiliumtrade.agiliumlabs.cloud",
            "useSharedClientApi": True,
            "eventProcessing": {"sequentialProcessing": request.param},
            "requestTimeout": 3,
            "retryOpts": {
                "retries": 3,
                "minDelayInSeconds": 0.1,
                "maxDelayInSeconds": 0.5,
                "subscribeCooldownInSeconds": 6,
            },
        },
    )

    async def side_effect_get_account(account_id):
        return {
            "_id": account_id,
            "login": "50194988",
            "name": "mt5a",
            "server": "ICMarketsSC-Demo",
            "region": "vint-hill",
            "reliability": "regular",
            "provisioningProfileId": "f9ce1f12-e720-4b9a-9477-c2d4cb25f076",
            "magic": 123456,
            "connectionStatus": "DISCONNECTED",
            "state": "DEPLOYED",
            "type": "cloud-g1",
        }

    api.metatrader_account_api._metatrader_account_client.get_account = AsyncMock(side_effect=side_effect_get_account)
    api._metaapi_websocket_client.set_url("http://localhost:8080")
    api._metaapi_websocket_client._socket_instances = {"vint-hill": {0: []}, "new-york": {0: []}}
    await api._metaapi_websocket_client.connect(0, "vint-hill")
    api._connection_registry._terminal_hash_manager._client_api_client.refresh_ignored_field_lists = AsyncMock()
    api._connection_registry._terminal_hash_manager._client_api_client.get_hashing_ignored_field_lists = MagicMock(
        return_value={
            "g1": {"specification": ["description"], "position": ["time"], "order": ["time"]},
            "g2": {"specification": ["pipSize"], "position": ["comment"], "order": ["comment"]},
        }
    )
    api._metaapi_websocket_client._resolved = True
    yield
    for task in asyncio.all_tasks():
        if task is not asyncio.tasks.current_task():
            task.cancel()
    await fake_server.stop()


def patch_wait_for(divider: float):
    async def patched_wait_for(fut, timeout=None):
        return await wait_for(fut, None if timeout is None else timeout / divider)

    return patched_wait_for


class TestSyncStability:
    @pytest.mark.asyncio
    async def test_sync(self):
        """Should synchronize account"""
        account = await api.metatrader_account_api.get_account("accountId")
        connection = account.get_streaming_connection()
        await connection.connect()
        await connection.wait_synchronized({"timeoutInSeconds": 10})
        response = connection.terminal_state.account_information
        assert response == account_information
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )

    @pytest.mark.asyncio
    async def test_socket_disconnect(self):
        """Should reconnect on server socket crash."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            await fake_server.sio.disconnect(fake_server.connections[0])
            await sleep(0.5)
            response = connection.terminal_state.account_information
            assert response == account_information
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_set_disconnected(self):
        """Should set state to disconnected on timeout."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.delete_status_task("accountId")

            @fake_server.sio.event
            async def connect(sid, environ):
                return False

            await fake_server.sio.disconnect(fake_server.connections[0])
            await sleep(1.2)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker

    @pytest.mark.asyncio
    async def test_resubscribe_on_timeout(self):
        """Should resubscribe on timeout."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.status_tasks["accountId"].cancel()
            await sleep(1.5)
            response = connection.terminal_state.account_information
            assert response == account_information
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_subscribe_with_late_response(self):
        """Should synchronize if subscribe response arrives after synchronization."""

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            if data["type"] == "subscribe":
                await sleep(0.2)
                fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                    fake_server.create_status_task(data["accountId"], fake_server.connections[0])
                )
                await fake_server.authenticate(data, sid)
                await sleep(0.4)
                await fake_server.respond(data, sid)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)

        account = await api.metatrader_account_api.get_account("accountId")
        connection = account.get_streaming_connection()
        await connection.connect()
        await connection.wait_synchronized({"timeoutInSeconds": 10})
        response = connection.terminal_state.account_information
        assert response == account_information
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )

    @pytest.mark.asyncio
    async def test_wait_redeploy(self):
        """Should wait until account is redeployed after disconnect."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.delete_status_task("accountId")
            fake_server.disable_sync()
            await sleep(0.05)
            await fake_server.sio.emit(
                "synchronization",
                {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
            )
            await sleep(0.4)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker
            await sleep(4)
            fake_server.enable_sync()
            await sleep(0.4)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker
            await sleep(4)
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_resubscribe_on_status_packet(self):
        """Should resubscribe immediately after disconnect on status packet."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.delete_status_task("accountId")
            await fake_server.sio.emit(
                "synchronization",
                {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
            )
            fake_server.disable_sync()
            await sleep(0.4)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker
            await sleep(4)
            fake_server.enable_sync()
            await fake_server.emit_status("accountId", fake_server.connections[0])
            await sleep(0.4)
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_resubscribe_on_reconnected_after_connection_closed(self):
        """Should resubscribe other accounts after one of connections is closed"""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 10})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            await connection3.wait_synchronized({"timeoutInSeconds": 10})
            await connection.close()
            fake_server.delete_status_task("accountId2")
            fake_server.delete_status_task("accountId3")
            fake_server.disable_sync()
            await fake_server.sio.disconnect(fake_server.connections[0])
            await sleep(2)
            fake_server.enable_sync()
            await fake_server.sio.disconnect(fake_server.connections[0])
            await sleep(8)
            assert not connection.synchronized
            assert (
                connection2.synchronized
                and connection2.terminal_state.connected
                and connection2.terminal_state.connected_to_broker
            )
            assert (
                connection3.synchronized
                and connection3.terminal_state.connected
                and connection3.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_429_per_user_limit_subscriptions(self):
        """Should limit subscriptions during per user 429 error."""
        subscribed_accounts = {}

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            nonlocal subscribed_accounts
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return
            if data["type"] == "subscribe":
                if len(subscribed_accounts.keys()) < 2:
                    subscribed_accounts[data["accountId"]] = True
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
                else:
                    await fake_server.emit_error(data, 1, 2)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                del subscribed_accounts[data["accountId"]]
                await fake_server.respond(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 3})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            try:
                await connection3.wait_synchronized({"timeoutInSeconds": 3})
                raise Exception("TimeoutException expected")
            except Exception as err:
                assert err.__class__.__name__ == "TimeoutException"
            await connection2.close()
            await sleep(2)
            assert connection3.synchronized

    @pytest.mark.asyncio
    async def test_429_per_user_retry_after_time(self):
        """Should wait for retry time after per user 429 error."""
        request_timestamp = 0
        subscribed_accounts = {}

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            nonlocal subscribed_accounts
            nonlocal request_timestamp
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return
            if data["type"] == "subscribe":
                if len(subscribed_accounts.keys()) < 2 or (
                    request_timestamp != 0 and datetime.now().timestamp() - 2 > request_timestamp
                ):
                    subscribed_accounts[data["accountId"]] = True
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
                else:
                    request_timestamp = datetime.now().timestamp()
                    await fake_server.emit_error(data, 1, 3)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                del subscribed_accounts[data["accountId"]]
                await fake_server.respond(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 3})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            try:
                await connection3.wait_synchronized({"timeoutInSeconds": 3})
                raise Exception("TimeoutException expected")
            except Exception as err:
                assert err.__class__.__name__ == "TimeoutException"
            await sleep(2)
            assert not connection3.synchronized
            await sleep(2.5)
            assert connection3.synchronized

    @pytest.mark.asyncio
    async def test_429_per_server_retry_after_time(self):
        """Should wait for retry time after per server 429 error."""
        sid_by_accounts = {}
        request_timestamp = 0

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            nonlocal request_timestamp
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return
            if data["type"] == "subscribe":
                if len(list(filter(lambda account_sid: account_sid == sid, sid_by_accounts.values()))) >= 2 and (
                    request_timestamp == 0 or datetime.now().timestamp() - 2 < request_timestamp
                ):
                    request_timestamp = datetime.now().timestamp()
                    await fake_server.emit_error(data, 2, 2)
                else:
                    sid_by_accounts[data["accountId"]] = sid
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 3})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            await connection3.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId2"] != sid_by_accounts["accountId3"]
            await sleep(2)
            account4 = await api.metatrader_account_api.get_account("accountId4")
            connection4 = account4.get_streaming_connection()
            await connection4.connect()
            await connection4.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId4"]

    @pytest.mark.asyncio
    async def test_429_per_server_reconnect(self):
        """Should reconnect after per server 429 error if connection has no subscribed accounts."""
        sids = []

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            if data["type"] == "subscribe":
                sids.append(sid)
                if len(sids) == 1:
                    await fake_server.emit_error(data, 2, 2)
                else:
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                fake_server.delete_status_task(data["accountId"])
                await fake_server.respond(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            assert sids[0] != sids[1]

    @pytest.mark.asyncio
    async def test_429_per_server_unsubscribe(self):
        """Should free a subscribe slot on unsubscribe after per server 429 error."""
        sid_by_accounts = {}

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return
            if data["type"] == "subscribe":
                if len(list(filter(lambda account_sid: account_sid == sid, sid_by_accounts.values()))) >= 2:
                    await fake_server.emit_error(data, 2, 200)
                else:
                    sid_by_accounts[data["accountId"]] = sid
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                del sid_by_accounts[data["accountId"]]
                await fake_server.respond(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 3})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            await connection3.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId2"] != sid_by_accounts["accountId3"]
            await connection2.close()
            account4 = await api.metatrader_account_api.get_account("accountId4")
            connection4 = account4.get_streaming_connection()
            await connection4.connect()
            await connection4.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId4"]

    @pytest.mark.asyncio
    async def test_429_per_server_per_user_retry_after_time(self):
        """Should wait for retry time after per server per user 429 error."""
        sid_by_accounts = {}
        request_timestamp = 0

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            nonlocal request_timestamp
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return
            if data["type"] == "subscribe":
                if len(list(filter(lambda account_sid: account_sid == sid, sid_by_accounts.values()))) >= 2 and (
                    request_timestamp == 0 or datetime.now().timestamp() - 2 < request_timestamp
                ):
                    request_timestamp = datetime.now().timestamp()
                    await fake_server.emit_error(data, 0, 2)
                else:
                    sid_by_accounts[data["accountId"]] = sid
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
            elif data["type"] == "synchronize":
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                del sid_by_accounts[data["accountId"]]
                await fake_server.respond(data, sid)

        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await connection2.wait_synchronized({"timeoutInSeconds": 3})
            account3 = await api.metatrader_account_api.get_account("accountId3")
            connection3 = account3.get_streaming_connection()
            await connection3.connect()
            await connection3.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId2"] != sid_by_accounts["accountId3"]
            await sleep(2)
            account4 = await api.metatrader_account_api.get_account("accountId4")
            connection4 = account4.get_streaming_connection()
            await connection4.connect()
            await connection4.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] != sid_by_accounts["accountId4"]
            await connection2.close()
            account5 = await api.metatrader_account_api.get_account("accountId5")
            connection5 = account5.get_streaming_connection()
            await connection5.connect()
            await connection5.wait_synchronized({"timeoutInSeconds": 3})
            assert sid_by_accounts["accountId"] == sid_by_accounts["accountId5"]

    @pytest.mark.asyncio
    async def test_resubscribe_on_disconnected_packet(self):
        """Should attempt to resubscribe on disconnected packet."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            assert connection.synchronized
            assert connection.terminal_state.connected
            assert connection.terminal_state.connected_to_broker
            fake_server.delete_status_task("accountId")
            await fake_server.sio.emit(
                "synchronization",
                {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
            )
            await sleep(0.2)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker
            await sleep(0.4)
            assert connection.synchronized
            assert connection.terminal_state.connected
            assert connection.terminal_state.connected_to_broker

    @pytest.mark.asyncio
    async def test_multiple_streams(self):
        """Should handle multiple streams in one instance number."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            subscribe_called = False

            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["type"] == "subscribe":
                    nonlocal subscribe_called
                    subscribe_called = True
                elif data["type"] == "synchronize":
                    await fake_server.respond(data, sid)
                    await fake_server.sync_account(data, sid, "ps-mpa-1")
                elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                    await fake_server.respond(data, sid)
                elif data["type"] == "getAccountInformation":
                    await fake_server.respond_account_information(data, sid)

            asyncio.create_task(fake_server.create_status_task("accountId", fake_server.connections[0], "ps-mpa-1"))
            await fake_server.authenticate({"accountId": "accountId"}, fake_server.connections[0], "ps-mpa-1")
            await sleep(0.4)
            fake_server.delete_status_task("accountId")
            await fake_server.sio.emit(
                "synchronization",
                {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
            )
            await sleep(0.2)
            assert connection.synchronized
            assert connection.terminal_state.connected
            assert connection.terminal_state.connected_to_broker
            assert not subscribe_called
            await fake_server.sio.emit(
                "synchronization",
                {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-1", "instanceIndex": 0},
            )
            await sleep(0.1)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker

    @pytest.mark.asyncio
    async def test_multiple_streams_timeout(self):
        """Should not resubscribe if multiple streams and one timed out."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            logger.debug('Start test')
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            subscribe_called = False

            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["type"] == "subscribe":
                    nonlocal subscribe_called
                    subscribe_called = True
                    logger.info(f"{sid}: overriden subscribe request called {json.dumps(data)}")
                elif data["type"] == "synchronize":
                    await fake_server.respond(data, sid)
                    await fake_server.sync_account(data, sid, "ps-mpa-1")
                elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                    await fake_server.respond(data, sid)
                elif data["type"] == "getAccountInformation":
                    await fake_server.respond_account_information(data, sid)

            logger.info('Stage 1')
            status_task = asyncio.create_task(
                fake_server.create_status_task("accountId", fake_server.connections[0], "ps-mpa-1")
            )
            await fake_server.authenticate({"accountId": "accountId"}, fake_server.connections[0], "ps-mpa-1")
            await sleep(0.1)
            fake_server.delete_status_task("accountId")
            await sleep(1.1)
            assert connection.synchronized
            assert connection.terminal_state.connected
            assert connection.terminal_state.connected_to_broker
            assert not subscribe_called
            logger.info('Stage 2')
            status_task.cancel()
            await sleep(1.1)
            assert not connection.synchronized
            assert not connection.terminal_state.connected
            assert not connection.terminal_state.connected_to_broker
            assert subscribe_called

    @pytest.mark.asyncio
    async def test_not_resubscribe_after_close(self):
        """Should not synchronize if connection is closed."""
        synchronize_counter = 0

        @fake_server.sio.event
        async def connect(sid, environ):
            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["type"] == "subscribe":
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
                elif data["type"] == "synchronize":
                    nonlocal synchronize_counter
                    synchronize_counter += 1
                    await fake_server.respond(data, sid)
                    await fake_server.sync_account(data, sid)
                elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                    await fake_server.respond(data, sid)
                elif data["type"] == "getAccountInformation":
                    await fake_server.respond_account_information(data, sid)
                elif data["type"] == "unsubscribe":
                    await fake_server.respond(data, sid)

            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 3})
            assert synchronize_counter == 1
            account2 = await api.metatrader_account_api.get_account("accountId2")
            connection2 = account2.get_streaming_connection()
            await connection2.connect()
            await sleep(0.1)
            await connection2.close()
            try:
                await connection2.wait_synchronized({"timeoutInSeconds": 3})
                raise Exception("TimeoutException expected")
            except Exception as err:
                assert err.args[0] == "This connection has been closed, please create a new connection"
            assert synchronize_counter == 1

    @pytest.mark.asyncio
    @patch('lib.clients.metaapi.metaapi_websocket_client.asyncio.wait_for', new=patch_wait_for(100))
    async def test_not_resubscribe_after_close_after_disconnected(self):
        """Should not resubscribe after connection is closed."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 100)):
            subscribe_counter = 0

            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["instanceIndex"] == 1:
                    await fake_server.respond(data, sid)
                    return
                if sid == fake_server.connections[0]:
                    if data["type"] == "subscribe":
                        nonlocal subscribe_counter
                        subscribe_counter += 1
                        await asyncio.sleep(0.1)
                        await fake_server.respond(data, sid)
                        fake_server.delete_status_task(data["accountId"])
                        fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                            fake_server.create_status_task(data["accountId"], sid)
                        )
                        await fake_server.authenticate(data, sid)
                    elif data["type"] == "synchronize":
                        await fake_server.respond(data, sid)
                        await fake_server.sync_account(data, sid)
                    elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                        await fake_server.respond(data, sid)
                    elif data["type"] == "getAccountInformation":
                        await fake_server.respond_account_information(data, sid)
                    elif data["type"] == "unsubscribe":
                        fake_server.delete_status_task(data["accountId"])
                        await fake_server.respond(data, sid)

            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            assert subscribe_counter == 1
            asyncio.create_task(
                fake_server.sio.emit(
                    "synchronization",
                    {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
                )
            )
            await sleep(0.1)
            assert subscribe_counter > 1
            previous_subscribe_counter = subscribe_counter
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            asyncio.create_task(
                fake_server.sio.emit(
                    "synchronization",
                    {"type": "disconnected", "accountId": "accountId", "host": "ps-mpa-0", "instanceIndex": 0},
                )
            )
            await asyncio.sleep(0.1)
            await connection.close()
            await sleep(0.1)
            assert subscribe_counter == previous_subscribe_counter
            assert not connection.synchronized
            assert not connection.terminal_state.connected

    @pytest.mark.asyncio
    async def test_not_resubscribe_on_timeout_if_connection_closed(self):
        """Should not resubscribe on timeout if connection is closed."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 100)):
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.status_tasks["accountId"].cancel()
            assert connection.synchronized
            await connection.close()
            await sleep(0.62)
            assert not connection.synchronized

    @pytest.mark.asyncio
    async def test_not_send_multiple_subscribes_on_status(self):
        """Should not send multiple subscribe requests if status arrives faster than subscribe."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            subscribe_calls = 0
            account = await api.metatrader_account_api.get_account("accountId")
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            fake_server.disable_sync()
            fake_server.status_tasks["accountId"].cancel()
            await sleep(2)
            assert (
                not connection.synchronized
                and not connection.terminal_state.connected
                and not connection.terminal_state.connected_to_broker
            )

            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["instanceIndex"] == 1:
                    await fake_server.respond(data, sid)
                    return

                if data["type"] == "subscribe":
                    nonlocal subscribe_calls
                    subscribe_calls += 1
                    await sleep(2.8)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
                elif data["type"] == "synchronize":
                    await fake_server.respond(data, sid)
                    await fake_server.sync_account(data, sid)
                elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                    await fake_server.respond(data, sid)
                elif data["type"] == "getAccountInformation":
                    await fake_server.respond_account_information(data, sid)
                elif data["type"] == "unsubscribe":
                    await fake_server.respond(data, sid)

            fake_server.status_tasks["accountId"] = asyncio.create_task(
                fake_server.create_status_task("accountId", fake_server.connections[0])
            )
            await sleep(4)
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            assert subscribe_calls == 1


class TestTerminalState:
    @pytest.mark.asyncio
    async def test_receive_updates_for_an_account(self):
        """Should receive updates for an account."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 1000)):
            with freeze_time() as frozen_datetime:
                positions_update = [
                    {
                        "id": "46214692",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "GBPUSD",
                        "magic": 1000,
                        "time": "2020-04-15T02:45:06.521Z",
                        "updateTime": "2020-04-15T02:45:06.521Z",
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214693",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "EURUSD",
                        "magic": 1000,
                        "time": "2020-04-15T02:45:06.521Z",
                        "updateTime": "2020-04-15T02:45:06.521Z",
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214694",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "AUDNZD",
                        "magic": 1000,
                        "time": "2020-04-15T02:45:06.521Z",
                        "updateTime": "2020-04-15T02:45:06.521Z",
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                ]
                orders_update = [
                    {
                        "id": "46871284",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "AUDNZD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": "2020-04-20T08:38:58.270Z",
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871285",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "EURUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": "2020-04-20T08:38:58.270Z",
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871286",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "BTCUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": "2020-04-20T08:38:58.270Z",
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                ]
                update = {
                    "type": "update",
                    "accountId": "accountId",
                    "instanceIndex": 0,
                    "host": "ps-mpa-0",
                    "accountInformation": {
                        "broker": "True ECN Trading Ltd",
                        "currency": "USD",
                        "server": "ICMarketsSC-Demo",
                        "balance": 7319.9,
                        "equity": 7306.649913200001,
                        "margin": 184.1,
                        "freeMargin": 7120.22,
                        "leverage": 100,
                        "marginLevel": 3967.58283542,
                    },
                    "updatedPositions": positions_update,
                    "removedPositionIds": [],
                    "updatedOrders": orders_update,
                    "completedOrderIds": [],
                    "historyOrders": [
                        {
                            "clientId": "TE_GBPUSD_7hyINWqAlE",
                            "currentPrice": 1.261,
                            "currentVolume": 0,
                            "doneTime": "2020-04-15T02:45:06.521Z",
                            "id": "46214692",
                            "magic": 1000,
                            "platform": "mt5",
                            "positionId": "46214692",
                            "state": "ORDER_STATE_FILLED",
                            "symbol": "GBPUSD",
                            "time": "2020-04-15T02:45:06.260Z",
                            "type": "ORDER_TYPE_BUY",
                            "volume": 0.07,
                        }
                    ],
                    "deals": [
                        {
                            "clientId": "TE_GBPUSD_7hyINWqAlE",
                            "commission": -0.25,
                            "entryType": "DEAL_ENTRY_IN",
                            "id": "33230099",
                            "magic": 1000,
                            "platform": "mt5",
                            "orderId": "46214692",
                            "positionId": "46214692",
                            "price": 1.26101,
                            "profit": 0,
                            "swap": 0,
                            "symbol": "GBPUSD",
                            "time": "2020-04-15T02:45:06.521Z",
                            "type": "DEAL_TYPE_BUY",
                            "volume": 0.07,
                        }
                    ],
                }

                account = await api.metatrader_account_api.get_account("accountId")
                connection = account.get_streaming_connection()
                await connection.connect()
                frozen_datetime.tick(5)
                await connection.wait_synchronized({"timeoutInSeconds": 10})
                await fake_server.sio.emit("synchronization", update)
                frozen_datetime.tick(5)
                await sleep(0.005)
                assert connection.terminal_state.orders == [
                    {
                        "id": "46871284",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "AUDNZD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871285",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "EURUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871286",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "BTCUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                ]
                assert connection.terminal_state.positions == [
                    {
                        "id": "46214692",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "GBPUSD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214693",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "EURUSD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214694",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "AUDNZD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                ]
                assert connection.terminal_state.specifications == [
                    {"maxVolume": 200, "minVolume": 0.01, "symbol": "EURUSD", "tickSize": 0.00001, "volumeStep": 0.01}
                ]

                update_2 = {
                    "type": "update",
                    "accountId": "accountId",
                    "instanceIndex": 0,
                    "host": "ps-mpa-0",
                    "updatedPositions": [
                        {
                            "id": "46214693",
                            "type": "POSITION_TYPE_BUY",
                            "symbol": "EURUSD",
                            "magic": 1000,
                            "time": "2020-04-15T02:45:06.521Z",
                            "updateTime": "2020-04-15T02:45:06.521Z",
                            "openPrice": 1.26101,
                            "currentPrice": 1.24883,
                            "currentTickValue": 1,
                            "volume": 0.07,
                            "swap": 0,
                            "profit": -85.25999999999966,
                            "commission": -0.25,
                            "clientId": "TE_GBPUSD_7hyINWqAlE",
                            "stopLoss": 1.18,
                            "unrealizedProfit": -85.25999999999901,
                            "realizedProfit": -6.536993168992922e-13,
                        },
                        {
                            "id": "46214695",
                            "type": "POSITION_TYPE_BUY",
                            "symbol": "BTCUSD",
                            "magic": 1000,
                            "time": "2020-04-15T02:45:06.521Z",
                            "updateTime": "2020-04-15T02:45:06.521Z",
                            "openPrice": 1.26101,
                            "currentPrice": 1.24883,
                            "currentTickValue": 1,
                            "volume": 0.07,
                            "swap": 0,
                            "profit": -85.25999999999966,
                            "commission": -0.25,
                            "clientId": "TE_GBPUSD_7hyINWqAlE",
                            "stopLoss": 1.17721,
                            "unrealizedProfit": -85.25999999999901,
                            "realizedProfit": -6.536993168992922e-13,
                        },
                    ],
                    "removedPositionIds": ["46214694"],
                    "updatedOrders": [
                        {
                            "id": "46871285",
                            "type": "ORDER_TYPE_BUY_LIMIT",
                            "state": "ORDER_STATE_PLACED",
                            "symbol": "EURUSD",
                            "magic": 123456,
                            "platform": "mt5",
                            "time": "2020-04-20T08:38:58.270Z",
                            "openPrice": 1.03,
                            "currentPrice": 1.05206,
                            "volume": 0.5,
                            "currentVolume": 0.01,
                            "comment": "COMMENT2",
                        },
                        {
                            "id": "46871287",
                            "type": "ORDER_TYPE_BUY_LIMIT",
                            "state": "ORDER_STATE_PLACED",
                            "symbol": "XAUUSD",
                            "magic": 123456,
                            "platform": "mt5",
                            "time": "2020-04-20T08:38:58.270Z",
                            "openPrice": 1.03,
                            "currentPrice": 1.05206,
                            "volume": 0.01,
                            "currentVolume": 0.01,
                            "comment": "COMMENT2",
                        },
                    ],
                    "completedOrderIds": ["46871286"],
                    "specifications": [
                        {"maxVolume": 200, "minVolume": 0.01, "symbol": "EURUSD", "tickSize": 0.01, "volumeStep": 0.01}
                    ],
                }

                await fake_server.sio.emit("synchronization", update_2)
                frozen_datetime.tick(5)
                await sleep(0.005)
                assert connection.terminal_state.orders == [
                    {
                        "id": "46871284",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "AUDNZD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871285",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "EURUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.5,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                    {
                        "id": "46871287",
                        "type": "ORDER_TYPE_BUY_LIMIT",
                        "state": "ORDER_STATE_PLACED",
                        "symbol": "XAUUSD",
                        "magic": 123456,
                        "platform": "mt5",
                        "time": date("2020-04-20T08:38:58.270Z"),
                        "openPrice": 1.03,
                        "currentPrice": 1.05206,
                        "volume": 0.01,
                        "currentVolume": 0.01,
                        "comment": "COMMENT2",
                    },
                ]
                assert connection.terminal_state.positions == [
                    {
                        "id": "46214692",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "GBPUSD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214693",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "EURUSD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.18,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                    {
                        "id": "46214695",
                        "type": "POSITION_TYPE_BUY",
                        "symbol": "BTCUSD",
                        "magic": 1000,
                        "time": date("2020-04-15T02:45:06.521Z"),
                        "updateTime": date("2020-04-15T02:45:06.521Z"),
                        "openPrice": 1.26101,
                        "currentPrice": 1.24883,
                        "currentTickValue": 1,
                        "volume": 0.07,
                        "swap": 0,
                        "profit": -85.25999999999966,
                        "commission": -0.25,
                        "clientId": "TE_GBPUSD_7hyINWqAlE",
                        "stopLoss": 1.17721,
                        "unrealizedProfit": -85.25999999999901,
                        "realizedProfit": -6.536993168992922e-13,
                    },
                ]


class TestSpecificationsSync:
    @pytest.mark.asyncio
    async def test_synchronize_two_accounts_with_similar_server_names_and_same_data(self):
        """Should synchronize two accounts with similar server names and same data."""
        with freeze_time() as frozen_datetime:

            async def get_account(account_id: str):
                return {
                    '_id': account_id,
                    'login': '50194988',
                    'name': 'mt5a',
                    'region': 'vint-hill',
                    'reliability': 'regular',
                    'server': 'ICMarketsSC-Demo' + account_id[9:],
                    'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                    'magic': 123456,
                    'application': 'MetaApi',
                    'connectionStatus': 'DISCONNECTED',
                    'state': 'DEPLOYED',
                    'type': 'cloud-g1',
                }

            api.metatrader_account_api._metatrader_account_client.get_account = get_account

            account = await api.metatrader_account_api.get_account('accountId')
            account_2 = await api.metatrader_account_api.get_account('accountId2')
            connection = account.get_streaming_connection()
            await connection.connect()
            frozen_datetime.tick(5)
            await connection.wait_synchronized({'timeoutInSeconds': 10})
            response = connection.terminal_state.account_information
            assert response == account_information
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            assert connection.terminal_state.specifications == default_specifications
            connection_2 = account_2.get_streaming_connection()
            await connection_2.connect()
            frozen_datetime.tick(5)
            await connection_2.wait_synchronized({'timeoutInSeconds': 10})
            assert connection_2.terminal_state.specifications == default_specifications

    @pytest.mark.asyncio
    async def test_synchronize_two_accounts_with_same_server_name(self):
        """Should synchronize two accounts with different specs and same server name."""
        with freeze_time() as frozen_datetime:
            specifications_2 = [
                {'symbol': 'AUDUSD', 'tickSize': 0.00001, 'minVolume': 0.01, 'maxVolume': 200, 'volumeStep': 0.01}
            ]

            @fake_server.sio.event
            async def connect(sid, environ):
                @fake_server.sio.on('request')
                async def on_request(sid, data):
                    if data['instanceIndex'] == 1:
                        await fake_server.respond(data, sid)
                        return

                    if data['type'] == 'subscribe':
                        await sleep(0.2)
                        await fake_server.respond(data, sid)
                        asyncio.create_task(fake_server.create_status_task(data['accountId'], sid))
                        await sleep(0.05)
                        await fake_server.authenticate(data, sid)
                    elif data['type'] == 'synchronize':
                        await fake_server.respond(data, sid)
                        if data['accountId'] == 'accountId2':
                            await fake_server.sync_account(data, sid, None, {'specifications': specifications_2})
                        else:
                            await fake_server.sync_account(data, sid)
                    elif data['type'] in ['waitSynchronized', 'refreshMarketDataSubscriptions']:
                        await fake_server.respond(data, sid)
                    elif data['type'] == 'getAccountInformation':
                        await fake_server.respond_account_information(data, sid)
                    elif data['type'] == 'unsubscribe':
                        fake_server.delete_status_task(data['accountId'])
                        await fake_server.respond(data, sid)

            account = await api.metatrader_account_api.get_account('accountId')
            account_2 = await api.metatrader_account_api.get_account('accountId2')
            connection = account.get_streaming_connection()
            await connection.connect()
            frozen_datetime.tick(5)
            await connection.wait_synchronized({'timeoutInSeconds': 10})
            await sleep(0.5)
            response = connection.terminal_state.account_information
            assert response == account_information
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            assert connection.terminal_state.specifications == default_specifications

            connection_2 = account_2.get_streaming_connection()
            await connection_2.connect()
            frozen_datetime.tick(5)
            await connection_2.wait_synchronized({'timeoutInSeconds': 10})
            assert connection_2.terminal_state.specifications == specifications_2

    @pytest.mark.asyncio
    async def test_synchronize_two_accounts_with_different_server_names(self):
        """Should synchronize two accounts with different specs and different server names."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 1000)):
            with freeze_time() as frozen_datetime:
                specifications_2 = [
                    {'symbol': 'AUDUSD', 'tickSize': 0.00001, 'minVolume': 0.01, 'maxVolume': 200, 'volumeStep': 0.01}
                ]

                async def get_account(account_id: str):
                    return {
                        '_id': account_id,
                        'login': '50194988',
                        'name': 'mt5a',
                        'region': 'vint-hill',
                        'reliability': 'regular',
                        'server': 'ICMarketsSC-Demo' if account_id == 'accountId' else 'Tradeview-Demo',
                        'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                        'magic': 123456,
                        'application': 'MetaApi',
                        'connectionStatus': 'DISCONNECTED',
                        'state': 'DEPLOYED',
                        'type': 'cloud-g1',
                    }

                api.metatrader_account_api._metatrader_account_client.get_account = get_account

                @fake_server.sio.event
                async def connect(sid, environ):
                    @fake_server.sio.on('request')
                    async def on_request(sid, data):
                        if data['instanceIndex'] == 1:
                            await fake_server.respond(data, sid)
                            return

                        if data['type'] == 'subscribe':
                            await sleep(0.0002)
                            await fake_server.respond(data, sid)
                            asyncio.create_task(fake_server.create_status_task(data['accountId'], sid))
                            await sleep(0.00005)
                            await fake_server.authenticate(data, sid)
                        elif data['type'] == 'synchronize':
                            await fake_server.respond(data, sid)
                            if data['accountId'] == 'accountId2':
                                await fake_server.sync_account(data, sid, None, {'specifications': specifications_2})
                            else:
                                await fake_server.sync_account(data, sid)
                        elif data['type'] in ['waitSynchronized', 'refreshMarketDataSubscriptions']:
                            await fake_server.respond(data, sid)
                        elif data['type'] == 'getAccountInformation':
                            await fake_server.respond_account_information(data, sid)
                        elif data['type'] == 'unsubscribe':
                            fake_server.delete_status_task(data['accountId'])
                            await fake_server.respond(data, sid)

                    account = await api.metatrader_account_api.get_account('accountId')
                    account_2 = await api.metatrader_account_api.get_account('accountId2')
                    connection = account.get_streaming_connection()
                    await connection.connect()
                    frozen_datetime.tick(5)
                    await connection.wait_synchronized({'timeoutInSeconds': 10})
                    await sleep(0.5)
                    response = connection.terminal_state.account_information
                    assert response == account_information
                    assert (
                        connection.synchronized
                        and connection.terminal_state.connected
                        and connection.terminal_state.connected_to_broker
                    )
                    assert connection.terminal_state.specifications == default_specifications

                    connection_2 = account_2.get_streaming_connection()
                    await connection_2.connect()
                    frozen_datetime.tick(5)
                    await connection_2.wait_synchronized({'timeoutInSeconds': 10})
                    assert connection_2.terminal_state.specifications == specifications_2

    @pytest.mark.asyncio
    @patch('lib.clients.metaapi.metaapi_websocket_client.asyncio.wait_for', new=patch_wait_for(100))
    async def test_connect_to_different_server_if_url_changed(self):
        """Should connect to a different server if url changed."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 100)):
            api._metaapi_websocket_client._url = None

            async def get_url_settings_mock(instance_number, region):
                await sleep(0.01)
                return {'url': 'http://localhost:8080', 'isSharedClientApi': True}

            api._metaapi_websocket_client.get_url_settings = AsyncMock(side_effect=get_url_settings_mock)
            account = await api.metatrader_account_api.get_account('accountId')
            connection = account.get_streaming_connection()
            await connection.connect()
            await connection.wait_synchronized({'timeoutInSeconds': 10})
            response = connection.terminal_state.account_information
            assert response == account_information
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

            fake_server_2 = FakeServer()
            await fake_server_2.start(6786)
            fake_server.delete_status_task('accountId')
            fake_server.disable_sync()
            await fake_server.close()

            await fake_server.sio.disconnect(fake_server.connections[0])
            await fake_server.runner.cleanup()

            await sleep(0.7)
            assert not (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

            async def get_url_settings_mock(instance_number, region):
                await sleep(0.01)
                return {'url': 'http://localhost:6786', 'isSharedClientApi': True}

            api._metaapi_websocket_client.get_url_settings = AsyncMock(side_effect=get_url_settings_mock)

            await sleep(1)
            await asyncio.sleep(0.05)

            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_handle_random_socket_events(self):
        """Should handle random socket events."""
        with freeze_time() as frozen_datetime:
            account = await api.metatrader_account_api.get_account('accountId')
            connection = account.get_streaming_connection()
            await connection.connect()
            frozen_datetime.tick(5)
            await connection.wait_synchronized({'timeoutInSeconds': 10})
            event_count = 100
            account_id = 'accountId'
            event_log = []
            history_storage = {
                'deals': connection.history_storage.deals,
                'historyOrders': connection.history_storage.history_orders,
            }
            states_positions = deepcopy(default_positions)
            for position in states_positions:
                position['time'] = date(position['time'])
                position['updateTime'] = date(position['updateTime'])

            states_orders = deepcopy(default_orders)
            for order in states_orders:
                order['time'] = date(order['time'])

            states = {
                'combined': {
                    'connected': False,
                    'accountInformation': account_information.copy(),
                    'positions': states_positions.copy(),
                    'orders': states_orders.copy(),
                    'specifications': default_specifications.copy(),
                },
                'vint-hill:0:ps-mpa-0': {
                    'connected': True,
                    'synced': True,
                    'positions': states_positions.copy(),
                    'orders': states_orders.copy(),
                    'specifications': default_specifications.copy(),
                },
            }

            for k in range(event_count):
                synchronization_id = 'ABC'
                number = floor(random() * 10)
                instance_index_number = floor(random() * 5)
                host = f"ps-mpa-{instance_index_number}"
                instance_index = f"vint-hill:0:{host}"

                if instance_index not in states:
                    states[instance_index] = {'connected': False, 'synced': False}

                account_info = {
                    'broker': 'True ECN Trading Ltd',
                    'currency': 'USD',
                    'server': 'ICMarketsSC-Demo',
                    'balance': floor(random() * 4500),
                    'equity': 7306.649913200001,
                    'margin': 184.1,
                    'freeMargin': 7120.22,
                    'leverage': 100,
                    'marginLevel': 3967.58283542,
                }
                random_id = str(1000000 + floor(random() * 1000000))
                deals = [
                    {
                        'clientId': 'TE_GBPUSD_7hyINWqAlE',
                        'commission': -0.25,
                        'entryType': 'DEAL_ENTRY_IN',
                        'id': random_id,
                        'magic': floor(random() * 1000),
                        'platform': 'mt5',
                        'orderId': '46214692',
                        'positionId': '46214692',
                        'price': 1.26101,
                        'profit': 0,
                        'swap': 0,
                        'symbol': 'GBPUSD',
                        'time': '2020-04-15T02:45:06.521Z',
                        'type': 'DEAL_TYPE_BUY',
                        'volume': 0.07,
                    }
                ]
                history_orders = [
                    {
                        'clientId': 'TE_GBPUSD_7hyINWqAlE',
                        'currentPrice': 1.261,
                        'currentVolume': 0,
                        'doneTime': '2020-04-15T02:45:06.521Z',
                        'id': random_id,
                        'magic': floor(random() * 1000),
                        'platform': 'mt5',
                        'positionId': '46214692',
                        'state': 'ORDER_STATE_FILLED',
                        'symbol': 'GBPUSD',
                        'time': '2020-04-15T02:45:06.260Z',
                        'type': 'ORDER_TYPE_BUY',
                        'volume': 0.07,
                    }
                ]
                specifications = [
                    {
                        'symbol': 'EURUSD',
                        'tickSize': 0.00001,
                        'minVolume': 0.01,
                        'maxVolume': floor(random() * 1000),
                        'volumeStep': 0.01,
                    }
                ]
                prices = [
                    {
                        'symbol': 'EURUSD',
                        'time': format_date(datetime.now()),
                        'bid': random() * 2,
                        'ask': random() * 2 - 0.1,
                        'profitTickValue': 0.602,
                        'lossTickValue': 0.60203,
                    }
                ]
                positions = [
                    {
                        'id': random_id,
                        'type': 'POSITION_TYPE_BUY',
                        'symbol': 'GBPUSD',
                        'magic': 1000,
                        'time': '2020-04-15T02:45:06.521Z',
                        'updateTime': '2020-04-15T02:45:06.521Z',
                        'openPrice': 1.26101,
                        'currentPrice': 1.24883,
                        'currentTickValue': 1,
                        'volume': 0.07,
                        'swap': 0,
                        'profit': -85.25999999999966,
                        'commission': -0.25,
                        'clientId': 'TE_GBPUSD_7hyINWqAlE',
                        'stopLoss': 1.17721,
                        'unrealizedProfit': -85.25999999999901,
                        'realizedProfit': -6.536993168992922e-13,
                    }
                ]
                orders = [
                    {
                        'id': random_id,
                        'type': 'ORDER_TYPE_BUY_LIMIT',
                        'state': 'ORDER_STATE_PLACED',
                        'symbol': 'AUDNZD',
                        'magic': floor(random() * 1000),
                        'platform': 'mt5',
                        'time': '2020-04-20T08:38:58.270Z',
                        'openPrice': 1.03,
                        'currentPrice': 1.05206,
                        'volume': 0.01,
                        'currentVolume': 0.01,
                        'comment': 'COMMENT2',
                    }
                ]
                update = {'updatedPositions': positions, 'updatedOrders': orders}
                equity = floor(random() * 1000)
                free_margin = floor(random() * 1000)
                margin_level = floor(random() * 1000)
                margin = floor(random() * 1000)

                if number == 0:
                    event_log.append(f"accountInformation:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            "type": 'accountInformation',
                            "accountId": account_id,
                            "accountInformation": account_info,
                            'instanceIndex': 0,
                            'host': host,
                        },
                    )
                    await sleep(0.5)
                    states['combined']['accountInformation'] = account_info
                elif number == 1:
                    global sync_host
                    sync_host = host
                    event_log.append(f"authenticated:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'authenticated',
                            'accountId': account_id,
                            'instanceIndex': 0,
                            'replicas': 1,
                            'host': host,
                        },
                    )
                    await sleep(0.5)
                    states[instance_index]['connected'] = True
                    states[instance_index]['synced'] = True
                    states['combined']['accountInformation'] = account_information.copy()
                    states['combined']['orders'] = states_orders.copy()
                    states['combined']['positions'] = states_positions.copy()
                    states['combined']['specifications'] = default_specifications.copy()
                    sync_host = 'ps-mpa-0'
                elif number == 2:
                    event_log.append(f"deals:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {'type': 'deals', 'accountId': account_id, 'deals': deals, 'instanceIndex': 0, 'host': host},
                    )
                    await sleep(0.5)
                    deal = deals[0].copy()
                    deal['time'] = date(deal['time'])
                    history_storage['deals'].append(deal)
                    history_storage['deals'].sort(key=lambda a: a['id'])
                elif number == 3:
                    event_log.append(f"historyOrders:{instance_index}")
                    await fake_server.sio.emit(
                        "synchronization",
                        {
                            'type': 'historyOrders',
                            'accountId': account_id,
                            'historyOrders': history_orders,
                            'instanceIndex': 0,
                            'host': host,
                        },
                    )
                    await sleep(0.5)
                    history_order = history_orders[0].copy()
                    history_order['time'] = date(history_order['time'])
                    history_order['doneTime'] = date(history_order['doneTime'])
                    history_storage['historyOrders'].append(history_order)
                    history_storage['historyOrders'].sort(key=lambda a: a['id'])
                elif number == 4:
                    event_log.append(f"dealSynchronizationFinished:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'dealSynchronizationFinished',
                            'accountId': account_id,
                            'host': host,
                            'instanceIndex': instance_index,
                            'synchronizationId': synchronization_id,
                        },
                    )
                elif number == 5:
                    event_log.append(f"orderSynchronizationFinished:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'orderSynchronizationFinished',
                            'accountId': account_id,
                            'host': host,
                            'instanceIndex': instance_index,
                            'synchronizationId': synchronization_id,
                        },
                    )
                elif number == 6:
                    event_log.append(f"downgradeSubscription:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'downgradeSubscription',
                            'accountId': account_id,
                            'host': host,
                            'instanceIndex': 0,
                            'symbol': 'EURUSD',
                            'unsubscriptions': [{'type': 'ticks'}, {'type': 'books'}],
                        },
                    )
                elif number == 7:
                    event_log.append(f"specifications:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'specifications',
                            'accountId': account_id,
                            'specifications': specifications,
                            'instanceIndex': 0,
                            'host': host,
                            'removedSymbols': [],
                        },
                    )
                    await sleep(0.5)
                    if states[instance_index].get('synced'):
                        states['combined']['specifications'] = specifications
                elif number == 8:
                    event_log.append(f"prices:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {
                            'type': 'prices',
                            'accountId': account_id,
                            'host': host,
                            'prices': prices,
                            'equity': equity,
                            'margin': margin,
                            'freeMargin': free_margin,
                            'marginLevel': margin_level,
                            'instanceIndex': 0,
                        },
                    )
                    await sleep(0.5)
                    states['combined']['accountInformation']['equity'] = equity
                    states['combined']['accountInformation']['margin'] = margin
                    states['combined']['accountInformation']['freeMargin'] = free_margin
                    states['combined']['accountInformation']['marginLevel'] = margin_level
                elif number == 9:
                    event_log.append(f"update:{instance_index}")
                    await fake_server.sio.emit(
                        'synchronization',
                        {'type': 'update', 'accountId': account_id, 'instanceIndex': 0, 'host': host, **update},
                    )
                    await sleep(0.5)
                    if states[instance_index].get('synced'):
                        position = update['updatedPositions'][0].copy()
                        position['time'] = date(position['time'])
                        position['updateTime'] = date(position['updateTime'])
                        states['combined']['positions'].append(position)
                        order = update['updatedOrders'][0]
                        order['time'] = date(order['time'])
                        states['combined']['orders'].append(order)
                try:
                    assert connection.terminal_state.specifications == states['combined']['specifications']
                    assert connection.terminal_state.account_information == states['combined']['accountInformation']
                    assert connection.terminal_state.positions == states['combined']['positions']
                    assert connection.terminal_state.orders == states['combined']['orders']
                    assert connection.history_storage.deals == history_storage['deals']
                    assert connection.history_storage.history_orders == history_storage['historyOrders']
                except Exception as error:
                    print(event_log[-50:], format_error(error))
                    raise error


@pytest.fixture
def get_account_mock():
    async def side_effect_get_account(account_id):
        return {
            "_id": account_id,
            "login": "50194988",
            "name": "mt5a",
            "region": "vint-hill",
            "reliability": "regular",
            "server": "ICMarketsSC-Demo",
            "provisioningProfileId": "f9ce1f12-e720-4b9a-9477-c2d4cb25f076",
            "magic": 123456,
            "connectionStatus": "CONNECTED",
            "state": "DEPLOYED",
            "type": "cloud-g1",
            "accountReplicas": [
                {
                    "_id": "accountIdReplica",
                    "quoteStreamingIntervalInSeconds": 2.5,
                    "region": "new-york",
                    "magic": 0,
                    "symbol": "EURUSD",
                    "copyFactoryResourceSlots": 1,
                    "resourceSlots": 1,
                    "extensions": [],
                    "tags": [],
                    "state": "DEPLOYED",
                    "connectionStatus": "CONNECTED",
                    "reliability": "regular",
                }
            ],
        }

    api.metatrader_account_api._metatrader_account_client.get_account = side_effect_get_account


class TestSyncReplica:
    @pytest.mark.asyncio
    async def test_sync(self, get_account_mock):
        """Should synchronize account."""
        account = await api.metatrader_account_api.get_account("accountId")
        connection = account.get_streaming_connection()
        await connection.connect()
        await connection.wait_synchronized({"timeoutInSeconds": 10})
        response = connection.terminal_state.account_information
        assert response == account_information
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )

    @pytest.mark.asyncio
    async def test_sync_replica(self, get_account_mock):
        """Should synchronize using a replica."""
        called_account_id = None
        unsubscribed_account_id = None
        allowed_accounts = ["accountId", "accountIdReplica"]

        account = await api.metatrader_account_api.get_account("accountId")

        @fake_server.sio.on("request")
        async def on_request(sid, data):
            if data["instanceIndex"] == 1:
                await fake_server.respond(data, sid)
                return

            if data["accountId"] not in allowed_accounts:
                return

            nonlocal called_account_id
            nonlocal unsubscribed_account_id

            if data["type"] == "subscribe":
                await sleep(0.2)
                await fake_server.respond(data, sid)
                fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                    fake_server.create_status_task(data["accountId"], sid)
                )
                await fake_server.authenticate(data, sid)
            elif data["type"] == "synchronize":
                called_account_id = data["accountId"]
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                called_account_id = data["accountId"]
                await fake_server.respond(data, sid)
            elif data["type"] == "getAccountInformation":
                await fake_server.respond_account_information(data, sid)
            elif data["type"] == "unsubscribe":
                unsubscribed_account_id = data["accountId"]
                fake_server.delete_status_task(data["accountId"])
                await fake_server.respond(data, sid)

        connection = account.get_streaming_connection()
        connection._websocket_client._latency_service._latency_cache = {"vint-hill": 500, "new-york": 100}
        await connection.connect()
        await connection.wait_synchronized({"timeoutInSeconds": 10})
        response = connection.terminal_state.account_information
        assert response == account_information
        assert called_account_id == "accountIdReplica"
        assert unsubscribed_account_id == "accountId"
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )

    @pytest.mark.asyncio
    async def test_resync_if_other_account_undeployed(self, get_account_mock):
        """Should resynchronize if used account was undeployed, then return when redeployed."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 50)):
            called_account_id = None
            unsubscribed_account_id = None
            allowed_accounts = ["accountId", "accountIdReplica"]

            account = await api.metatrader_account_api.get_account("accountId")

            @fake_server.sio.on("request")
            async def on_request(sid, data):
                if data["instanceIndex"] == 1:
                    await fake_server.respond(data, sid)
                    return

                if data["accountId"] not in allowed_accounts:
                    return

                nonlocal called_account_id
                nonlocal unsubscribed_account_id

                if data["type"] == "subscribe":
                    await sleep(0.2)
                    await fake_server.respond(data, sid)
                    fake_server.status_tasks[data["accountId"]] = asyncio.create_task(
                        fake_server.create_status_task(data["accountId"], sid)
                    )
                    await fake_server.authenticate(data, sid)
                elif data["type"] == "synchronize":
                    called_account_id = data["accountId"]
                    await fake_server.respond(data, sid)
                    await fake_server.sync_account(data, sid)
                elif data["type"] in ["waitSynchronized", "refreshMarketDataSubscriptions"]:
                    called_account_id = data["accountId"]
                    await fake_server.respond(data, sid)
                elif data["type"] == "getAccountInformation":
                    await fake_server.respond_account_information(data, sid)
                elif data["type"] == "unsubscribe":
                    unsubscribed_account_id = data["accountId"]
                    fake_server.delete_status_task(data["accountId"])
                    await fake_server.respond(data, sid)

            connection = account.get_streaming_connection()
            connection._websocket_client._latency_service._latency_cache = {"vint-hill": 500, "new-york": 100}
            await connection.connect()
            await connection.wait_synchronized({"timeoutInSeconds": 10})
            response = connection.terminal_state.account_information
            assert response == account_information
            assert called_account_id == "accountIdReplica"
            assert unsubscribed_account_id == "accountId"
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

            allowed_accounts = allowed_accounts[:1]
            fake_server.delete_status_task("accountIdReplica")
            await sleep(1.3)
            assert unsubscribed_account_id == "accountId"
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )
            allowed_accounts.append("accountIdReplica")
            await fake_server.emit_status("accountIdReplica", fake_server.connections[0])
            await sleep(0.5)
            assert called_account_id == "accountIdReplica"
            assert unsubscribed_account_id == "accountId"
            assert (
                connection.synchronized
                and connection.terminal_state.connected
                and connection.terminal_state.connected_to_broker
            )

    @pytest.mark.asyncio
    async def test_change_replica_if_region_priority_changed(self, get_account_mock):
        """Should change replica if region priority changed."""
        called_account_id = None
        unsubscribed_account_id = None

        account = await api.metatrader_account_api.get_account('accountId')

        @fake_server.sio.on('request')
        async def on_request(sid, data):
            if data['instanceIndex'] == 1:
                await fake_server.respond(data, sid)
                return

            nonlocal called_account_id
            nonlocal unsubscribed_account_id

            if data['type'] == 'subscribe':
                await asyncio.sleep(0.2)
                await fake_server.respond(data, sid)
                fake_server.status_tasks[data['accountId']] = asyncio.create_task(
                    fake_server.create_status_task(data['accountId'], sid)
                )
                await fake_server.authenticate(data, sid)
            elif data['type'] == 'synchronize':
                called_account_id = data['accountId']
                await fake_server.respond(data, sid)
                await fake_server.sync_account(data, sid)
            elif data['type'] in ['waitSynchronized', 'refreshMarketDataSubscriptions']:
                called_account_id = data['accountId']
                await fake_server.respond(data, sid)
            elif data['type'] == 'getAccountInformation':
                await fake_server.respond_account_information(data, sid)
            elif data['type'] == 'unsubscribe':
                unsubscribed_account_id = data['accountId']
                fake_server.delete_status_task(data['accountId'])
                await fake_server.respond(data, sid)

        connection = account.get_streaming_connection()
        connection._websocket_client._latency_service._refresh_latency = AsyncMock()
        connection._websocket_client._latency_service._latency_cache = {'vint-hill': 500, 'new-york': 100}
        await connection.connect()
        await connection.wait_synchronized({'timeoutInSeconds': 10})
        response = connection.terminal_state.account_information
        assert response == account_information
        assert called_account_id == 'accountIdReplica'
        assert unsubscribed_account_id == 'accountId'
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )
        connection._websocket_client._latency_service._latency_cache = {'vint-hill': 100, 'new-york': 500}
        await connection._websocket_client._latency_service._refresh_latency_job()
        await sleep(1)
        assert called_account_id == 'accountId'
        assert unsubscribed_account_id == 'accountIdReplica'
        assert (
            connection.synchronized
            and connection.terminal_state.connected
            and connection.terminal_state.connected_to_broker
        )

    @pytest.mark.asyncio
    @patch('lib.clients.metaapi.metaapi_websocket_client.asyncio.wait_for', new=patch_wait_for(120))
    async def test_close_account_on_not_found_exception(self):
        """Should close the account on NotFoundException."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 200)):
            with patch('lib.metaapi.metaapi_connection.random', new=lambda: 0.002):
                account = await api.metatrader_account_api.get_account('accountId')
                connection = account.get_streaming_connection()
                await connection.connect()
                await connection.wait_synchronized({'timeoutInSeconds': 101})

                @fake_server.sio.on('request')
                async def on_request(sid, data):
                    pass

                api.metatrader_account_api._metatrader_account_client.get_account = AsyncMock(
                    side_effect=NotFoundException('test')
                )
                fake_server.disable_sync()
                fake_server.delete_status_task('accountId')
                fake_server.delete_status_task('accountIdReplica')

                for socket in fake_server.connections:
                    asyncio.create_task(fake_server.sio.disconnect(socket))

                await sleep(1)
                assert connection._closed
                assert (
                    not connection.synchronized
                    and not connection.terminal_state.connected
                    and not connection.terminal_state.connected_to_broker
                )

    @pytest.mark.asyncio
    @patch('lib.clients.metaapi.metaapi_websocket_client.asyncio.wait_for', new=patch_wait_for(120))
    async def test_update_replica_list(self):
        """Should update replica list."""
        with patch("lib.clients.metaapi.metaapi_websocket_client.asyncio.sleep", new=lambda x: sleep(x / 120)):
            with patch('lib.metaapi.metaapi_connection.random', new=lambda: 0.002):

                async def get_account(account_id: str):
                    return {
                        '_id': account_id,
                        'login': '50194988',
                        'name': 'mt5a',
                        'region': 'vint-hill',
                        'reliability': 'regular',
                        'server': 'ICMarketsSC-Demo',
                        'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                        'magic': 123456,
                        'application': 'MetaApi',
                        'connectionStatus': 'DISCONNECTED',
                        'state': 'DEPLOYED',
                        'type': 'cloud-g1',
                        'accountReplicas': [
                            {
                                '_id': 'accountIdReplica',
                                'state': 'DEPLOYED',
                                'magic': 0,
                                'connectionStatus': 'CONNECTED',
                                'quoteStreamingIntervalInSeconds': 2.5,
                                'reliability': 'high',
                                'tags': [],
                                'resourceSlots': 1,
                                'copyFactoryResourceSlots': 1,
                                'region': 'new-york',
                                'createdAt': '2023-08-31T19:45:14.001Z',
                            },
                            {
                                '_id': 'london-replica',
                                'state': 'DEPLOYED',
                                'magic': 0,
                                'connectionStatus': 'CONNECTED',
                                'quoteStreamingIntervalInSeconds': 2.5,
                                'reliability': 'high',
                                'tags': [],
                                'resourceSlots': 1,
                                'copyFactoryResourceSlots': 1,
                                'region': 'london',
                                'createdAt': '2023-08-31T19:45:14.001Z',
                            },
                        ],
                    }

                api.metatrader_account_api._metatrader_account_client.get_account = AsyncMock(side_effect=get_account)

                account = await api.metatrader_account_api.get_account('accountId')
                connection = account.get_streaming_connection()
                await connection.connect()
                await connection.wait_synchronized({'timeoutInSeconds': 101})

                @fake_server.sio.event
                async def connect(sid, environ):
                    @fake_server.sio.on('request')
                    async def on_request(sid, data):
                        if data.get('accountId') == 'singapore-replica':
                            if data['instanceIndex'] == 1:
                                await fake_server.respond(data, sid)
                                return

                            if data['type'] == 'subscribe':
                                await asyncio.sleep(0.2)
                                asyncio.create_task(fake_server.create_status_task(data['accountId'], sid))
                                await fake_server.authenticate(data, sid)
                                await asyncio.sleep(0.4)
                                await fake_server.respond(data, sid)
                            elif data['type'] == 'synchronize':
                                await fake_server.respond(data, sid)
                                await fake_server.sync_account(data, sid)
                            elif data['type'] in ['waitSynchronized', 'refreshMarketDataSubscriptions']:
                                await fake_server.respond(data, sid)
                            elif data['type'] == 'getAccountInformation':
                                await fake_server.respond_account_information(data, sid)

                async def get_account(account_id: str):
                    return {
                        '_id': account_id,
                        'login': '50194988',
                        'name': 'mt5a',
                        'region': 'vint-hill',
                        'reliability': 'regular',
                        'server': 'ICMarketsSC-Demo',
                        'provisioningProfileId': 'f9ce1f12-e720-4b9a-9477-c2d4cb25f076',
                        'magic': 123456,
                        'application': 'MetaApi',
                        'connectionStatus': 'DISCONNECTED',
                        'state': 'DEPLOYED',
                        'type': 'cloud-g1',
                        'accountReplicas': [
                            {
                                '_id': 'london-replica',
                                'state': 'DEPLOYED',
                                'magic': 0,
                                'connectionStatus': 'CONNECTED',
                                'quoteStreamingIntervalInSeconds': 2.5,
                                'reliability': 'high',
                                'tags': [],
                                'resourceSlots': 1,
                                'copyFactoryResourceSlots': 1,
                                'region': 'london',
                                'createdAt': '2023-08-31T19:45:14.001Z',
                            },
                            {
                                '_id': 'singapore-replica',
                                'state': 'DEPLOYED',
                                'magic': 0,
                                'connectionStatus': 'CONNECTED',
                                'quoteStreamingIntervalInSeconds': 2.5,
                                'reliability': 'high',
                                'tags': [],
                                'resourceSlots': 1,
                                'copyFactoryResourceSlots': 1,
                                'region': 'singapore',
                                'createdAt': '2023-08-31T19:45:14.001Z',
                            },
                        ],
                    }

                api.metatrader_account_api._metatrader_account_client.get_account = AsyncMock(side_effect=get_account)

                fake_server.disable_sync()
                fake_server.delete_status_task('accountId')
                fake_server.delete_status_task('accountIdReplica')

                for socket in fake_server.connections:
                    asyncio.create_task(fake_server.sio.disconnect(socket))

                await asyncio.sleep(0.05)
                await sleep(1)
                await asyncio.sleep(0.05)
                await sleep(1)

                assert (
                    connection.synchronized
                    and connection.terminal_state.connected
                    and connection.terminal_state.connected_to_broker
                )
