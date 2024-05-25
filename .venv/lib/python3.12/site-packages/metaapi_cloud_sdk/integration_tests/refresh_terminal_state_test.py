import asyncio
import json
import os
from logging import Logger
from typing import Union

import pytest

from lib import MetaApi
from lib.logger import LoggerManager, NativeLogger
from lib.metaapi.metatrader_account import MetatraderAccount
from lib.metaapi.rpc_metaapi_connection_instance import RpcMetaApiConnectionInstance
from lib.metaapi.streaming_metaapi_connection_instance import StreamingMetaApiConnectionInstance

token = os.getenv('TOKEN')
login = os.getenv('LOGIN')
password = os.getenv('PASSWORD')
server_name = os.getenv('SERVER')

if not token:
    pytest.skip(allow_module_level=True)

api: MetaApi = None
logger: Union[Logger, NativeLogger] = None
account: MetatraderAccount = None


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


async def prepare_account() -> MetatraderAccount:
    """Prepares metatrader account for test.

    Returns:
        A coroutine resolving with test account.
    """
    accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination()
    result = None
    for account in accounts:
        if account.login == login and account.type.startswith('cloud-g2'):
            result = account
            break

    if not result:
        result = await api.metatrader_account_api.create_account(
            {
                'name': 'Test account',
                'type': 'cloud-g2',
                'login': login,
                'password': password,
                'server': server_name,
                'application': 'MetaApi',
                'platform': 'mt5',
                'magic': 1000,
            }
        )

    await result.deploy()
    await result.wait_connected()
    return result


@pytest.fixture(scope="module", autouse=True)
async def run_before_tests():
    MetaApi.enable_logging()
    global api
    api = MetaApi(token, {'domain': 'agiliumtrade.gfyt.agiliumlabs.cloud'})

    global logger
    logger = LoggerManager.get_logger('test')

    global account
    account = await prepare_account()

    yield

    api.close()


@pytest.fixture
async def streaming_connection():
    global account
    connection = account.get_streaming_connection()
    await connection.connect()
    await connection.wait_synchronized()
    yield connection
    await connection.close()


class TestRefreshTerminalStateStreamingConnection:
    @pytest.mark.asyncio
    async def test_refresh_terminal_state_with_streaming_api(
        self, streaming_connection: StreamingMetaApiConnectionInstance
    ):
        """Should refresh terminal state with streaming api."""
        await streaming_connection.subscribe_to_market_data('BTCUSD', [{'type': 'quotes'}])
        await streaming_connection.terminal_state.refresh_terminal_state()


@pytest.fixture()
async def rpc_connection():
    global account
    connection = account.get_rpc_connection()
    await connection.connect()
    await connection.wait_synchronized()
    yield connection
    await connection.close()


class TestRefreshTerminalStateRPCConnection:
    @pytest.mark.asyncio
    async def test_retrieve_refreshed_symbol_quotes(self, rpc_connection: RpcMetaApiConnectionInstance):
        """Should retrieve refreshed symbol quotes."""
        refreshed_quotes = await rpc_connection.refresh_symbol_quotes(['BTCUSD'])
        logger.info(f"Received refreshed quotes {json.dumps(refreshed_quotes)}")

    @pytest.mark.asyncio
    async def test_retrieve_account_information_error_with_refreshing_terminal_state(
        self, rpc_connection: RpcMetaApiConnectionInstance
    ):
        """Should retrieve account information error with refreshing terminal state."""
        account_information = await rpc_connection.get_account_information({'refreshTerminalState': True})
        logger.info(f"Received account information {json.dumps(account_information)}")
