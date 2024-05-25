import asyncio
from asyncio import sleep
from datetime import datetime
from typing import List, Union

import pytest
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory, StepTickTimeFactory
from mock.mock import patch, MagicMock

from lib.clients.metaapi.client_api_client import ClientApiClient, HashingIgnoredFieldLists
from lib.metaapi.metatrader_account import MetatraderAccount
from lib.metaapi.models import MetatraderSymbolSpecification, MetatraderPosition, MetatraderOrder, date
from lib.metaapi.terminal_hash_manager import TerminalHashManager
from lib.metaapi.terminal_state import TerminalState

terminal_hash_manager: TerminalHashManager = None
state: TerminalState = None
accounts: List[MetatraderAccount] = None

specifications: List[MetatraderSymbolSpecification] = None
updated_specifications: List[MetatraderSymbolSpecification] = None
updated_specifications_2: List[MetatraderSymbolSpecification] = None

positions: List[MetatraderPosition] = None
updated_positions: List[MetatraderPosition] = None
updated_positions_2: List[MetatraderPosition] = None

orders: List[MetatraderOrder] = None
updated_orders: List[MetatraderOrder] = None
updated_orders_2: List[MetatraderOrder] = None


class MockClientApiClient(ClientApiClient):
    def get_hashing_ignored_field_lists(self, region: str) -> HashingIgnoredFieldLists:
        return {
            "g1": {
                "specification": [
                    "description",
                    "expirationTime",
                    "expirationBrokerTime",
                    "startTime",
                    "startBrokerTime",
                    "pipSize",
                ],
                "position": [
                    "time",
                    "updateTime",
                    "comment",
                    "brokerComment",
                    "originalComment",
                    "clientId",
                    "profit",
                    "realizedProfit",
                    "unrealizedProfit",
                    "currentPrice",
                    "currentTickValue",
                    "accountCurrencyExchangeRate",
                    "updateSequenceNumber",
                ],
                "order": [
                    "time",
                    "expirationTime",
                    "comment",
                    "brokerComment",
                    "originalComment",
                    "clientId",
                    "currentPrice",
                    "accountCurrencyExchangeRate",
                    "updateSequenceNumber",
                ],
            },
            "g2": {
                "specification": ["pipSize"],
                "position": [
                    "comment",
                    "brokerComment",
                    "originalComment",
                    "clientId",
                    "profit",
                    "realizedProfit",
                    "unrealizedProfit",
                    "currentPrice",
                    "currentTickValue",
                    "accountCurrencyExchangeRate",
                    "updateSequenceNumber",
                ],
                "order": [
                    "comment",
                    "brokerComment",
                    "originalComment",
                    "clientId",
                    "currentPrice",
                    "accountCurrencyExchangeRate",
                    "updateSequenceNumber",
                ],
            },
        }


def get_mock_metatrader_account(id: str, server: str, type: str):
    class MockAccount(MetatraderAccount):
        def __init__(
            self, data, metatrader_account_client, meta_api_websocket_client, connection_registry, application
        ):
            super(MockAccount, self).__init__(
                data,
                metatrader_account_client,
                meta_api_websocket_client,
                connection_registry,
                MagicMock(),
                MagicMock(),
                application,
            )
            self._state = 'DEPLOYED'

        @property
        def id(self):
            return id

        @property
        def server(self) -> str:
            return server

        @property
        def type(self) -> str:
            return type

    return MockAccount(MagicMock(), MagicMock(), MagicMock(), MagicMock(), 'MetaApi')


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch("lib.metaapi.terminal_state.asyncio.sleep", new=lambda x: sleep(x / 1000)):
        global accounts
        accounts = [
            get_mock_metatrader_account('accountId', 'ICMarkets-Demo1', 'cloud-g1'),
            get_mock_metatrader_account('accountId2', 'ICMarkets-Demo1', 'cloud-g1'),
            get_mock_metatrader_account('accountId3', 'ICMarkets-Demo2', 'cloud-g2'),
            get_mock_metatrader_account('accountId4', 'FXChoice', 'cloud-g2'),
            get_mock_metatrader_account('accountId5', 'FXChoice', 'cloud-g2'),
        ]
        client_api_client = MockClientApiClient(MagicMock(), MagicMock())
        global terminal_hash_manager
        terminal_hash_manager = TerminalHashManager(client_api_client)
        global state
        state = TerminalState(accounts[0], terminal_hash_manager, MagicMock())
        global specifications
        specifications = [{'symbol': 'EURUSD', 'tickSize': 0.00001}]
        global positions
        positions = [
            {
                'id': '1',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            }
        ]
        global orders
        orders = [{'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9}]
        global updated_specifications
        updated_specifications = [{'symbol': 'XAUUSD', 'tickSize': 0.001}]
        global updated_specifications_2
        updated_specifications_2 = [{'symbol': 'AUDUSD', 'tickSize': 0.002}]
        global updated_positions
        updated_positions = [
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 10,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            }
        ]
        global updated_positions_2
        updated_positions_2 = [
            {
                'id': '4',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 12,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            }
        ]
        global updated_orders
        updated_orders = [{'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 10}]
        global updated_orders_2
        updated_orders_2 = [{'id': '4', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 10}]
        yield
        for task in asyncio.all_tasks():
            if task is not asyncio.tasks.current_task():
                task.cancel()


def check_state(
    specifications_value: List = None, positions_value: List = None, orders_value: List = None, terminal=None
):
    if not terminal:
        terminal = state
    assert terminal.specifications == (specifications_value or [])
    assert terminal.positions == (positions_value or [])
    assert terminal.orders == (orders_value or [])


async def optimize_trees(frozen_datetime: Union[FrozenDateTimeFactory, StepTickTimeFactory]):
    frozen_datetime.tick(1500)
    await sleep(1.5)


class TestTerminal:
    @pytest.mark.asyncio
    async def test_synchronize_for_first_time_and_modify_account_state(self):
        """Should synchronize for the first time and modify account state."""
        with freeze_time() as frozen_datetime:
            frozen_datetime.move_to(datetime.fromtimestamp(0))
            check_state()

            assert state.specification('EURUSD') is None

            await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
            check_state()
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
            await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
            check_state()
            await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
            check_state()
            await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state()
            await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
            check_state()
            await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state(specifications, positions, orders)
            await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, [])
            check_state(specifications, [positions[0], updated_positions[0]], orders)
            await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, [])
            check_state(specifications, [positions[0], updated_positions[0]], [orders[0], updated_orders[0]])
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', updated_specifications, [])
            check_state(
                [specifications[0], updated_specifications[0]],
                [positions[0], updated_positions[0]],
                [orders[0], updated_orders[0]],
            )
            await state.on_positions_updated('vint-hill:1:ps-mpa-1', [], ['1'])
            check_state(
                [specifications[0], updated_specifications[0]], [updated_positions[0]], [orders[0], updated_orders[0]]
            )
            await optimize_trees(frozen_datetime)
            check_state(
                [specifications[0], updated_specifications[0]], [updated_positions[0]], [orders[0], updated_orders[0]]
            )

    @pytest.mark.asyncio
    async def test_synchronize_with_empty_state_and_modify(self):
        """Should synchronize with empty state and then modify."""
        check_state()
        assert state.specification('EURUSD') is None
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
        check_state()
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [], [])
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        check_state()
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', [])
        check_state()
        await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        check_state()
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', [])
        check_state()
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        check_state()
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, [])
        check_state([], updated_positions, [])
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, [])
        check_state([], updated_positions, updated_orders)
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', updated_specifications, [])
        check_state(updated_specifications, updated_positions, updated_orders)
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', [], ['1'])
        check_state(updated_specifications, [updated_positions[0]], updated_orders)
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [], ['1'])
        check_state([updated_specifications[0]], [updated_positions[0]], updated_orders)
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', [], ['1'])
        check_state([updated_specifications[0]], [updated_positions[0]], [updated_orders[0]])

    @pytest.mark.asyncio
    async def test_synchronize_two_accounts_using_same_data(self):
        """Should synchronize two accounts using the same data and then diverge."""
        with freeze_time() as frozen_datetime:
            await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
            await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
            await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
            await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
            await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state(specifications, positions, orders)
            state_2 = TerminalState(accounts[1], terminal_hash_manager, MagicMock())
            await state_2.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
            await state_2.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
            await state_2.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
            await state_2.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
            await state_2.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            await state_2.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
            await state_2.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state(specifications, positions, orders)
            check_state(specifications, positions, orders, state_2)
            await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, [])
            await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, [])
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', updated_specifications, [])
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            await state_2.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            check_state(
                [specifications[0], updated_specifications[0]],
                [positions[0], updated_positions[0]],
                [orders[0], updated_orders[0]],
            )
            check_state(specifications, positions, orders, state_2)
            await optimize_trees(frozen_datetime)
            check_state(
                [specifications[0], updated_specifications[0]],
                [positions[0], updated_positions[0]],
                [orders[0], updated_orders[0]],
            )
            check_state(specifications, positions, orders, state_2)
            await state_2.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions_2, [])
            check_state(specifications, [positions[0], updated_positions_2[0]], orders, state_2)
            await state_2.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders_2, [])
            check_state(
                specifications, [positions[0], updated_positions_2[0]], [orders[0], updated_orders_2[0]], state_2
            )
            await state_2.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', updated_specifications_2, [])
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            await state_2.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            check_state(
                [specifications[0], updated_specifications[0]],
                [positions[0], updated_positions[0]],
                [orders[0], updated_orders[0]],
            )
            check_state(
                [specifications[0], updated_specifications_2[0]],
                [positions[0], updated_positions_2[0]],
                [orders[0], updated_orders_2[0]],
                state_2,
            )
            await optimize_trees(frozen_datetime)
            check_state(
                [specifications[0], updated_specifications[0]],
                [positions[0], updated_positions[0]],
                [orders[0], updated_orders[0]],
            )
            check_state(
                [specifications[0], updated_specifications_2[0]],
                [positions[0], updated_positions_2[0]],
                [orders[0], updated_orders_2[0]],
                state_2,
            )

    @pytest.mark.asyncio
    async def test_synchronize_two_accounts_on_different_hashes(self):
        """Should synchronize two accounts on different hashes."""
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        check_state(specifications, positions, orders)
        specifications_2 = [{'symbol': 'AUDUSD', 'tickSize': 0.00001}]
        positions_2 = [
            {
                'id': '3',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 10,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            }
        ]
        orders_2 = [{'id': '3', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9}]
        state_2 = TerminalState(accounts[1], terminal_hash_manager, MagicMock())
        await state_2.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
        await state_2.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications_2, [])
        await state_2.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state_2.on_positions_replaced('vint-hill:1:ps-mpa-1', positions_2)
        await state_2.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state_2.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders_2)
        await state_2.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        check_state(specifications, positions, orders)
        check_state(specifications_2, positions_2, orders_2, state_2)

    @pytest.mark.asyncio
    async def test_synchronize_account_after_long_disconnect(self):
        """Should synchronize account after long disconnect."""
        with freeze_time() as frozen_datetime:
            await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
            await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
            await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
            await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
            await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state(specifications, positions, orders)
            await state.on_stream_closed('vint-hill:1:ps-mpa-1')
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', False)
            check_state(specifications, positions, orders)
            await optimize_trees(frozen_datetime)
            await optimize_trees(frozen_datetime)
            last_specs_hashes = terminal_hash_manager.get_last_used_specification_hashes('ICMarkets-Demo1')
            last_positions_hashes = terminal_hash_manager.get_last_used_position_hashes('accountId')
            last_orders_hashes = terminal_hash_manager.get_last_used_order_hashes('accountId')
            check_state([], [], [])
            await state.on_synchronization_started(
                'vint-hill:1:ps-mpa-1',
                last_specs_hashes[0],
                last_positions_hashes[0],
                last_orders_hashes[0],
                'synchronizationId2',
            )
            await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId2')
            await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId2')
            check_state(specifications, positions, orders)

    @pytest.mark.asyncio
    async def test_synchronize_account_with_empty_state(self):
        """Should synchronize account with empty state and then send data."""
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        check_state([], [], [])
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', positions, [])
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', orders, [])
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
        check_state(specifications, positions, orders)

    @pytest.mark.asyncio
    async def test_call_events_before_sync_finishes(self):
        """Should call events before sync finishes."""
        now = datetime.now().timestamp()
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now), 'symbol': 'EURUSD', 'bid': 1, 'ask': 1.1}]
        )
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.1), 'symbol': 'EURUSD', 'bid': 1.1, 'ask': 1.1}]
        )
        await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.2), 'symbol': 'EURUSD', 'bid': 1.2, 'ask': 1.1}]
        )
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.3), 'symbol': 'EURUSD', 'bid': 1.2, 'ask': 1.1}]
        )
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.4), 'symbol': 'EURUSD', 'bid': 1.3, 'ask': 1.1}]
        )
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.5), 'symbol': 'EURUSD', 'bid': 1.3, 'ask': 1.1}]
        )
        check_state(specifications, positions, orders)

    @pytest.mark.asyncio
    async def test_process_events_on_disconnected_account(self):
        """Should process events on a disconnected account."""
        with freeze_time() as frozen_datetime:
            now = datetime.now().timestamp()
            await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None, 'synchronizationId')
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', specifications, [])
            await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
            await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
            await state.on_positions_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
            await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
            check_state(specifications, positions, orders)
            await state.on_stream_closed('vint-hill:1:ps-mpa-1')
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', False)
            check_state(specifications, positions, orders)
            await optimize_trees(frozen_datetime)
            await optimize_trees(frozen_datetime)
            check_state([], [], [])
            await state.on_symbol_prices_updated(
                'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.5), 'symbol': 'EURUSD', 'bid': 1.3, 'ask': 1.1}]
            )
            await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, [])
            await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, [])
            await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', updated_specifications, [])
            await state.on_symbol_prices_updated(
                'vint-hill:1:ps-mpa-1', [{'time': date(now + 0.5), 'symbol': 'EURUSD', 'bid': 1.4, 'ask': 1.1}]
            )

    @pytest.mark.asyncio
    async def test_call_random_events(self):
        """Should call random events."""
        pass
