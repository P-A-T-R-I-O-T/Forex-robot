import asyncio
from asyncio import sleep
from datetime import datetime
from typing import Dict, List

import pytest
from freezegun import freeze_time
from mock.mock import MagicMock, AsyncMock, patch

from .metatrader_account import MetatraderAccount
from .models import MetatraderPosition, MetatraderSymbolSpecification, MetatraderOrder
from .terminal_hash_manager import TerminalHashManager
from .terminal_state import TerminalState
from ..clients.metaapi.metaapi_websocket_client import MetaApiWebsocketClient
from ..clients.timeout_exception import TimeoutException
from ..metaapi.models import date


class MockAccount(MetatraderAccount):
    def __init__(self, data, metatrader_account_client, meta_api_websocket_client, connection_registry, application):
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
        return 'accountId'

    @property
    def server(self) -> str:
        return 'ICMarkets-Demo1'

    @property
    def type(self) -> str:
        return 'cloud-g1'


class MockTerminalHashManager(TerminalHashManager):
    def get_specifications_by_hash(self, specification_hash: str) -> Dict[str, MetatraderSymbolSpecification]:
        pass

    def get_positions_by_hash(self, positions_hash: str) -> Dict[str, MetatraderPosition]:
        pass

    def get_orders_by_hash(self, orders_hash: str) -> Dict[str, MetatraderOrder]:
        pass

    def record_specifications(
        self,
        server_name: str,
        account_type: str,
        connection_id: str,
        instance_index: str,
        specifications: List[MetatraderSymbolSpecification],
    ) -> str:
        pass

    def record_orders(
        self, account_id: str, account_type: str, connection_id: str, instance_index: str, orders: List[MetatraderOrder]
    ) -> str:
        pass

    def record_positions(
        self,
        account_id: str,
        account_type: str,
        connection_id: str,
        instance_index: str,
        positions: List[MetatraderPosition],
    ) -> str:
        pass

    def update_orders(
        self,
        account_id: str,
        account_type: str,
        connection_id: str,
        instance_index: str,
        orders: List[MetatraderOrder],
        completed_orders: List[str],
        parent_hash: str,
    ) -> str:
        pass

    def update_positions(
        self,
        account_id: str,
        account_type: str,
        connection_id: str,
        instance_index: str,
        positions: List[MetatraderPosition],
        removed_positions: List[str],
        parent_hash: str,
    ) -> str:
        pass

    def update_specifications(
        self,
        server_name: str,
        account_type: str,
        connection_id: str,
        instance_index: str,
        specifications: List[MetatraderSymbolSpecification],
        removed_symbols: List[str],
        parent_hash: str,
    ) -> str:
        pass

    def get_last_used_order_hashes(self, account_id: str) -> List[str]:
        pass

    def get_last_used_position_hashes(self, account_id: str) -> List[str]:
        pass

    def get_last_used_specification_hashes(self, server_name: str) -> List[str]:
        pass

    def remove_connection_references(self, connection_id: str, instance_index: str):
        pass

    def add_specification_reference(self, hash: str, connection_id: str, instance_index: str):
        pass

    def remove_specification_reference(self, connection_id: str, instance_index: str):
        pass

    def add_position_reference(self, hash: str, connection_id: str, instance_index: str):
        pass

    def remove_position_reference(self, connection_id: str, instance_index: str):
        pass

    def add_order_reference(self, hash: str, connection_id: str, instance_index: str):
        pass

    def remove_order_reference(self, connection_id: str, instance_index: str):
        pass


account: MockAccount = None
terminal_hash_manager: MockTerminalHashManager = None
state: TerminalState = None
websocket_client: MetaApiWebsocketClient = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch('lib.metaapi.terminal_state.asyncio.sleep', new=lambda x: sleep(x / 1000)):
        global terminal_hash_manager
        terminal_hash_manager = MockTerminalHashManager(MagicMock())
        terminal_hash_manager.get_positions_by_hash = MagicMock(return_value={'1': {'id': '1', 'profit': 10}})
        terminal_hash_manager.get_orders_by_hash = MagicMock(return_value={'1': {'id': '1', 'openPrice': 10}})
        terminal_hash_manager.get_specifications_by_hash = MagicMock(
            return_value={'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.00001}}
        )
        global account
        account = MockAccount(MagicMock(), MagicMock(), MagicMock(), MagicMock(), 'MetaApi')
        global websocket_client
        websocket_client = MetaApiWebsocketClient(MagicMock(), MagicMock(), MagicMock())
        global state
        state = TerminalState(account, terminal_hash_manager, websocket_client)
        yield


class TestTerminalState:
    @pytest.mark.asyncio
    async def test_return_connection_state(self):
        """Should return connection state."""
        assert not state.connected
        await state.on_connected('vint-hill:1:ps-mpa-1', 1)
        assert state.connected
        await state.on_disconnected('vint-hill:1:ps-mpa-1')
        assert not state.connected

    @pytest.mark.asyncio
    async def test_return_broker_connection_state(self):
        """Should return broker connection state."""
        assert not state.connected_to_broker
        await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
        assert state.connected_to_broker
        await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', False)
        assert not state.connected_to_broker
        await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
        await state.on_disconnected('vint-hill:1:ps-mpa-1')
        assert not state.connected_to_broker

    @pytest.mark.asyncio
    async def test_clear_combined_state_on_disconnected_for_long_time(self):
        """Should clear combined state if account has been disconnected for a long time."""
        with freeze_time() as frozen_datetime:
            terminal_hash_manager.remove_connection_references = MagicMock()
            await state.on_account_information_updated(1, {'balance': 1000})
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', False)

            frozen_datetime.tick(1740)
            await sleep(0.174)
            assert state.account_information == {'balance': 1000}
            terminal_hash_manager.remove_connection_references.assert_not_called()

            frozen_datetime.tick(420)
            await sleep(0.42)
            assert state.account_information is None
            terminal_hash_manager.remove_connection_references.assert_called_with(state.id, 'combined')

    @pytest.mark.asyncio
    async def test_no_clear_combined_state_if_connection_status_changed_recently(self):
        """Should not clear combined state if connection status changed recently."""
        with freeze_time() as frozen_datetime:
            terminal_hash_manager.remove_connection_references = MagicMock()
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            await state.on_account_information_updated(1, {'balance': 1000})

            frozen_datetime.tick(1740)
            await sleep(0.174)
            assert state.account_information == {'balance': 1000}
            terminal_hash_manager.remove_connection_references.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_clear_combined_state_if_account_connected_for_long_time(self):
        """Should not clear combined state if connection status changed recently."""
        with freeze_time() as frozen_datetime:
            terminal_hash_manager.remove_connection_references = MagicMock()
            await state.on_broker_connection_status_changed('vint-hill:1:ps-mpa-1', True)
            await state.on_account_information_updated(1, {'balance': 1000})

            frozen_datetime.tick(3600)
            await sleep(0.36)
            assert state.account_information == {'balance': 1000}
            terminal_hash_manager.remove_connection_references.assert_not_called()

    @pytest.mark.asyncio
    async def test_return_account_information(self):
        """Should return account information."""
        assert not state.account_information
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        assert state.account_information == {'balance': 1000}

    @pytest.mark.asyncio
    async def test_return_positions(self):
        """Should return positions."""
        assert len(state.positions) == 0
        state._combined_state['positionsHash'] = 'hash1'
        assert len(state.positions) == 1
        assert state.positions == [{'id': '1', 'profit': 10}]

    @pytest.mark.asyncio
    async def test_return_orders(self):
        """Should return orders."""
        assert len(state.orders) == 0
        state._combined_state['ordersHash'] = 'hash1'
        assert len(state.orders) == 1
        assert state.orders == [{'id': '1', 'openPrice': 10}]

    @pytest.mark.asyncio
    async def test_return_specifications(self):
        """Should return specifications."""
        assert len(state.specifications) == 0
        state._combined_state['specificationsHash'] = 'hash1'
        assert len(state.specifications) == 1
        assert state.specifications == [{'symbol': 'EURUSD', 'tickSize': 0.00001}]

    @pytest.mark.asyncio
    async def test_update_positions(self):
        """Should update positions."""
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
        changed_position = {
            'id': '1',
            'symbol': 'EURUSD',
            'type': 'POSITION_TYPE_BUY',
            'currentPrice': 9,
            'currentTickValue': 0.5,
            'openPrice': 8,
            'profit': 100,
            'volume': 1,
        }
        terminal_hash_manager.record_positions = MagicMock(return_value='phash1')
        terminal_hash_manager.update_positions = MagicMock(return_value='phash2')
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', positions
        )
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', [changed_position], [])
        terminal_hash_manager.update_positions.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [changed_position], [], 'phash1'
        )
        assert terminal_hash_manager.update_positions.call_count == 2
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', [], ['1'])
        terminal_hash_manager.update_positions.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [], ['1'], 'phash2'
        )
        assert terminal_hash_manager.update_positions.call_count == 4

    @pytest.mark.asyncio
    async def test_record_positions_if_they_expected(self):
        """Should only record positions if they're expected."""
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
        terminal_hash_manager.record_positions = AsyncMock(return_value='phash1')
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, 'phash1', None)
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_positions.assert_not_called()

        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', positions
        )

    @pytest.mark.asyncio
    async def test_update_positions_that_not_on_removed_list(self):
        """Should only update positions that aren't on removed list."""
        await sleep(0.0001)
        positions = [
            {
                'id': '1',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 1,
            },
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            },
            {
                'id': '3',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 3,
            },
        ]
        updated_positions = [
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 3,
            },
            {
                'id': '3',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 4,
            },
            {
                'id': '4',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 5,
            },
        ]
        updated_positions_2 = [
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 3,
            },
            {
                'id': '4',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 5,
            },
            {
                'id': '5',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 5,
            },
        ]
        terminal_hash_manager.record_positions = MagicMock(return_value='phash1')
        terminal_hash_manager.update_positions = MagicMock(return_value='phash2')
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', positions
        )

        await state.on_positions_updated('vint-hill:1:ps-mpa-1', [], ['2'])

        terminal_hash_manager.update_positions.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [], ['2'], 'phash1'
        )

        await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, [])

        terminal_hash_manager.update_positions.assert_any_call(
            'accountId',
            'cloud-g1',
            state.id,
            'vint-hill:1:ps-mpa-1',
            [updated_positions[1], updated_positions[2]],
            [],
            'phash2',
        )

        await state.on_synchronization_started('vint-hill:1:ps-mpa-2', None, None, None)
        await state.on_positions_replaced('vint-hill:1:ps-mpa-2', updated_positions_2)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-2', 'synchronizationId2')

        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-2', [updated_positions_2[1], updated_positions_2[2]]
        )

    @pytest.mark.asyncio
    async def test_process_positions_update_events_during_sync(self):
        """Should process positions update events during sync."""
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
            },
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 3,
            },
            {
                'id': '3',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 11,
                'currentTickValue': 0.5,
                'openPrice': 9,
                'profit': 100,
                'volume': 4,
            },
        ]
        updated_positions = [
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 5,
            },
            {
                'id': '4',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 17,
            },
        ]
        expected_positions = [
            {
                'id': '1',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            },
            {
                'id': '2',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 5,
            },
            {
                'id': '4',
                'symbol': 'EURUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 17,
            },
        ]
        terminal_hash_manager.record_positions = AsyncMock(return_value='phash1')
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_positions_updated('vint-hill:1:ps-mpa-1', updated_positions, ['3'])
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', expected_positions
        )

    @pytest.mark.asyncio
    async def test_update_orders(self):
        """Should update orders."""
        orders = [{'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9}]
        changed_order = {'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 10}
        terminal_hash_manager.record_orders = MagicMock(return_value='ohash1')
        terminal_hash_manager.update_orders = MagicMock(return_value='ohash2')
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', orders
        )
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', [changed_order], [])
        terminal_hash_manager.update_orders.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [changed_order], [], 'ohash1'
        )
        assert terminal_hash_manager.update_orders.call_count == 2
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', [], ['1'])
        terminal_hash_manager.update_orders.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [], ['1'], 'ohash2'
        )
        assert terminal_hash_manager.update_orders.call_count == 4

    @pytest.mark.asyncio
    async def test_process_order_update_events_during_sync(self):
        """Should process order update events during sync."""
        orders = [
            {'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9},
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 10},
            {'id': '3', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 12},
        ]
        updated_orders = [
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 12},
            {'id': '4', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 16},
        ]
        expected_orders = [
            {'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9},
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 12},
            {'id': '4', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 16},
        ]
        terminal_hash_manager.record_orders = AsyncMock(return_value='ohash1')
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, ['3'])
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', expected_orders
        )

    @pytest.mark.asyncio
    async def test_record_orders_if_they_expected(self):
        """Should only record orders if they're expected."""
        orders = [{'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9}]
        terminal_hash_manager.record_orders = AsyncMock(return_value='ohash')
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, 'ohash1')
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_orders.assert_not_called()

        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', orders
        )

    @pytest.mark.asyncio
    async def test_update_orders_that_not_on_removed_list(self):
        """Should only update orders that aren't on removed list."""
        await sleep(0.0001)
        orders = [
            {'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 1},
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 2},
            {'id': '3', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 3},
        ]
        updated_orders = [
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 3},
            {'id': '3', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 4},
            {'id': '4', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 5},
        ]
        updated_orders_2 = [
            {'id': '2', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 3},
            {'id': '4', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 5},
            {'id': '5', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 5},
        ]
        terminal_hash_manager.record_orders = MagicMock(return_value='ohash1')
        terminal_hash_manager.update_orders = MagicMock(return_value='ohash2')
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', orders
        )

        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', [], ['2'])

        terminal_hash_manager.update_orders.assert_any_call(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [], ['2'], 'ohash1'
        )

        await state.on_pending_orders_updated('vint-hill:1:ps-mpa-1', updated_orders, [])

        terminal_hash_manager.update_orders.assert_any_call(
            'accountId',
            'cloud-g1',
            state.id,
            'vint-hill:1:ps-mpa-1',
            [updated_orders[1], updated_orders[2]],
            [],
            'ohash2',
        )

        await state.on_synchronization_started('vint-hill:1:ps-mpa-2', None, None, None)
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-2', updated_orders_2)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-2', 'synchronizationId2')

        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-2', [updated_orders_2[1], updated_orders_2[2]]
        )

    @pytest.mark.asyncio
    async def test_return_price(self):
        """Should return price."""
        assert not state.price('EURUSD')
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': date('2022-01-01T00:00:00.000Z'),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'bid': 1,
                    'ask': 1.1,
                }
            ],
        )
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [{'time': date('2022-01-01T00:00:01.000Z'), 'brokerTime': '2022-01-01 02:00:01.000', 'symbol': 'GBPUSD'}],
        )
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': date('2022-01-01T00:00:02.000Z'),
                    'brokerTime': '2022-01-01 02:00:02.000',
                    'symbol': 'EURUSD',
                    'bid': 1,
                    'ask': 1.2,
                }
            ],
        )
        assert state.price('EURUSD') == {
            'time': date('2022-01-01T00:00:02.000Z'),
            'symbol': 'EURUSD',
            'brokerTime': '2022-01-01 02:00:02.000',
            'bid': 1,
            'ask': 1.2,
        }
        assert state.last_quote_time == {
            'time': date('2022-01-01T00:00:02.000Z'),
            'brokerTime': '2022-01-01 02:00:02.000',
        }

    @pytest.mark.asyncio
    async def test_wait_for_price(self):
        """Should wait for price."""
        assert state.price('EURUSD') is None
        promise = asyncio.create_task(state.wait_for_price('EURUSD'))
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': date('2022-01-01 02:00:00.000'),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'bid': 1,
                    'ask': 1.1,
                }
            ],
        )
        assert (await promise) == {
            'time': date('2022-01-01 02:00:00.000'),
            'brokerTime': '2022-01-01 02:00:00.000',
            'symbol': 'EURUSD',
            'bid': 1,
            'ask': 1.1,
        }

    @pytest.mark.asyncio
    async def test_update_account_equity_and_position(self):
        """Should update account equity and position profit on price update."""
        await state.on_account_information_updated(
            'vint-hill:1:ps-mpa-1', {'equity': 1000, 'balance': 800, 'platform': 'mt4'}
        )
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
            },
            {
                'id': '2',
                'symbol': 'AUDUSD',
                'type': 'POSITION_TYPE_BUY',
                'currentPrice': 9,
                'currentTickValue': 0.5,
                'openPrice': 8,
                'profit': 100,
                'volume': 2,
            },
        ]
        state._combined_state['positionsHash'] = 'hash1'
        state._combined_state['specificationsHash'] = 'hash1'
        terminal_hash_manager.get_positions_by_hash = MagicMock(return_value={'1': positions[0], '2': positions[1]})
        terminal_hash_manager.get_specifications_by_hash = MagicMock(
            return_value={
                'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.01, 'digits': 5},
                'AUDUSD': {'symbol': 'AUDUSD', 'tickSize': 0.01, 'digits': 5},
            }
        )
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': datetime.now(),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'profitTickValue': 0.5,
                    'lossTickValue': 0.5,
                    'bid': 10,
                    'ask': 11,
                },
                {
                    'time': datetime.now(),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'AUDUSD',
                    'profitTickValue': 0.5,
                    'lossTickValue': 0.5,
                    'bid': 10,
                    'ask': 11,
                },
            ],
        )
        assert list(map(lambda p: p['profit'], state.positions)) == [200, 200]
        assert list(map(lambda p: p['unrealizedProfit'], state.positions)) == [200, 200]
        assert list(map(lambda p: p['currentPrice'], state.positions)) == [10, 10]
        assert state.account_information['equity'] == 1200

    @pytest.mark.asyncio
    async def test_update_margin_fields(self):
        """Should update margin fields on price update."""
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'equity': 1000, 'balance': 800})
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': datetime.now(),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'bid': 1,
                    'ask': 1.1,
                }
            ],
            100,
            200,
            400,
            40000,
        )
        assert state.account_information['equity'] == 100
        assert state.account_information['margin'] == 200
        assert state.account_information['freeMargin'] == 400
        assert state.account_information['marginLevel'] == 40000

    @pytest.mark.asyncio
    async def test_update_order_current_price_on_price_update(self):
        """Should update order currentPrice on price update."""

        terminal_hash_manager.get_orders_by_hash = MagicMock(
            return_value={
                '1': {'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9},
                '2': {'id': '2', 'symbol': 'AUDUSD', 'type': 'ORDER_TYPE_SELL_LIMIT', 'currentPrice': 9},
            }
        )
        state._combined_state['ordersHash'] = 'hash1'

        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': datetime.now(),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'profitTickValue': 0.5,
                    'lossTickValue': 0.5,
                    'bid': 10,
                    'ask': 11,
                }
            ],
        )
        assert list(map(lambda o: o['currentPrice'], state.orders)) == [11, 9]

    @pytest.mark.asyncio
    async def test_close_stream(self):
        """Should remove state on closed stream."""
        assert not state.price('EURUSD')
        await state.on_symbol_prices_updated(
            'vint-hill:1:ps-mpa-1',
            [
                {
                    'time': datetime.fromtimestamp(1000000),
                    'brokerTime': '2022-01-01 02:00:00.000',
                    'symbol': 'EURUSD',
                    'bid': 1,
                    'ask': 1.1,
                }
            ],
        )
        assert state.price('EURUSD') == {
            'time': datetime.fromtimestamp(1000000),
            'brokerTime': '2022-01-01 02:00:00.000',
            'symbol': 'EURUSD',
            'bid': 1,
            'ask': 1.1,
        }
        await state.on_disconnected('vint-hill:1:ps-mpa-1')

    @pytest.mark.asyncio
    async def test_on_synchronization_started(self):
        """Should process sync started and sync finished event."""
        terminal_hash_manager.record_specifications = AsyncMock()
        terminal_hash_manager.record_orders = AsyncMock()
        terminal_hash_manager.record_positions = AsyncMock()
        terminal_hash_manager.add_specification_reference = MagicMock()
        terminal_hash_manager.remove_specification_reference = MagicMock()
        terminal_hash_manager.add_position_reference = MagicMock()
        terminal_hash_manager.remove_position_reference = MagicMock()
        terminal_hash_manager.add_order_reference = MagicMock()
        terminal_hash_manager.remove_order_reference = MagicMock()

        specification = {'symbol': 'EURUSD', 'tickSize': 0.01}
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
        orders = [{'id': '1', 'symbol': 'EURUSD', 'type': 'ORDER_TYPE_BUY_LIMIT', 'currentPrice': 9}]
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        terminal_hash_manager.record_specifications.assert_not_called()
        terminal_hash_manager.record_orders.assert_not_called()
        terminal_hash_manager.record_positions.assert_not_called()
        terminal_hash_manager.add_specification_reference.assert_not_called()
        terminal_hash_manager.remove_specification_reference.assert_not_called()
        terminal_hash_manager.add_position_reference.assert_not_called()
        terminal_hash_manager.remove_position_reference.assert_not_called()
        terminal_hash_manager.add_order_reference.assert_not_called()
        terminal_hash_manager.remove_order_reference.assert_not_called()
        await state.on_synchronization_started(
            'vint-hill:1:ps-mpa-1', specifications_hash=None, positions_hash=None, orders_hash=None
        )
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [specification], [])
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        terminal_hash_manager.record_specifications.assert_called_with(
            'ICMarkets-Demo1', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [specification]
        )
        terminal_hash_manager.record_orders.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', orders
        )
        terminal_hash_manager.record_positions.assert_called_with(
            'accountId', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', positions
        )
        await state.on_synchronization_started(
            'vint-hill:1:ps-mpa-1', specifications_hash=None, positions_hash=None, orders_hash=None
        )
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [specification], [])
        await state.on_positions_replaced('vint-hill:1:ps-mpa-1', positions)
        await state.on_pending_orders_replaced('vint-hill:1:ps-mpa-1', orders)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        assert terminal_hash_manager.record_specifications.call_count == 2
        assert terminal_hash_manager.record_orders.call_count == 2
        assert terminal_hash_manager.record_positions.call_count == 2
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', 'shash1', 'phash1', 'ohash1')
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        assert terminal_hash_manager.record_specifications.call_count == 2
        assert terminal_hash_manager.record_orders.call_count == 2
        assert terminal_hash_manager.record_positions.call_count == 2
        terminal_hash_manager.add_specification_reference.assert_any_call('shash1', state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.add_specification_reference.assert_any_call('shash1', state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.add_specification_reference.assert_any_call('shash1', state.id, 'combined')
        terminal_hash_manager.remove_specification_reference.assert_any_call(state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.remove_specification_reference.assert_any_call(state.id, 'combined')
        terminal_hash_manager.add_position_reference.assert_any_call('phash1', state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.add_position_reference.assert_any_call('phash1', state.id, 'combined')
        terminal_hash_manager.remove_position_reference.assert_any_call(state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.remove_position_reference.assert_any_call(state.id, 'combined')
        terminal_hash_manager.add_order_reference.assert_any_call('ohash1', state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.add_order_reference.assert_any_call('ohash1', state.id, 'combined')
        terminal_hash_manager.remove_order_reference.assert_any_call(state.id, 'vint-hill:1:ps-mpa-1')
        terminal_hash_manager.remove_order_reference.assert_any_call(state.id, 'combined')

    @pytest.mark.asyncio
    async def test_return_hashes(self):
        """Should return hashes."""
        terminal_hash_manager.get_last_used_specification_hashes = MagicMock(return_value=['shash1', 'shash2'])
        terminal_hash_manager.get_last_used_position_hashes = MagicMock(return_value=['phash1', 'phash2'])
        terminal_hash_manager.get_last_used_order_hashes = MagicMock(return_value=['ohash1', 'ohash2'])
        hashes = state.get_hashes()
        assert hashes == {
            'specificationsHashes': ['shash1', 'shash2'],
            'positionsHashes': ['phash1', 'phash2'],
            'ordersHashes': ['ohash1', 'ohash2'],
        }
        terminal_hash_manager.get_last_used_specification_hashes.assert_called_with('ICMarkets-Demo1')
        terminal_hash_manager.get_last_used_position_hashes.assert_called_with('accountId')
        terminal_hash_manager.get_last_used_order_hashes.assert_called_with('accountId')

    @pytest.mark.asyncio
    async def test_return_specification_by_symbol(self):
        """Should return specification by symbol."""
        terminal_hash_manager.record_specifications = AsyncMock(return_value='shash1')
        expected_spec = {'symbol': 'EURUSD', 'tickSize': 0.00001}
        specification = state.specification('EURUSD')
        assert specification is None
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [expected_spec], [])
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')
        specification = state.specification('EURUSD')
        assert specification == {'symbol': 'EURUSD', 'tickSize': 0.00001}

    @pytest.mark.asyncio
    async def test_update_specifications_if_they_recorded_with_existing_hash(self):
        """Should update specifications if they're recorded with existing hash."""
        expected_spec = {'symbol': 'EURUSD', 'tickSize': 0.00001}
        expected_spec_2 = {'symbol': 'AUDUSD', 'tickSize': 0.00001}
        terminal_hash_manager.record_specifications = AsyncMock('shash1')
        terminal_hash_manager.update_specifications = AsyncMock('shash1')
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', None, None, None)
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-1', [expected_spec], [])
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId')

        terminal_hash_manager.record_specifications.assert_called_with(
            'ICMarkets-Demo1', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-1', [expected_spec]
        )
        terminal_hash_manager.update_specifications.assert_not_called()

        await state.on_synchronization_started('vint-hill:1:ps-mpa-2', 'shash1', None, None)
        await state.on_symbol_specifications_updated('vint-hill:1:ps-mpa-2', [expected_spec_2], [])
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-2', 'synchronizationId')

        terminal_hash_manager.update_specifications.assert_called_with(
            'ICMarkets-Demo1', 'cloud-g1', state.id, 'vint-hill:1:ps-mpa-2', [expected_spec_2], [], 'shash1'
        )

    @pytest.mark.asyncio
    async def test_delete_unfinished_states_except_latest_on_sync_started(self):
        """Should delete all unfinished states except for the latest on sync started."""
        await state.on_account_information_updated('vint-hill:2:ps-mpa-3', {'balance': 1000})
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_account_information_updated('vint-hill:1:ps-mpa-2', {'balance': 1000})
        await state.on_synchronization_started('vint-hill:1:ps-mpa-4', True, True, True)
        assert 'vint-hill:1:ps-mpa-1' in state._state_by_instance_index
        assert 'vint-hill:1:ps-mpa-2' not in state._state_by_instance_index
        assert 'vint-hill:2:ps-mpa-3' in state._state_by_instance_index

    @pytest.mark.asyncio
    async def test_delete_disconnected_states_on_sync_finished(self):
        """Should delete all disconnected states on sync finished."""
        await state.on_account_information_updated('vint-hill:2:ps-mpa-3', {'balance': 1000})
        await state.on_pending_orders_synchronized('vint-hill:2:ps-mpa-3', 'synchronizationId')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-1', 1)
        await state.on_account_information_updated('vint-hill:1:ps-mpa-2', {'balance': 1000})
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-2', 'synchronizationId2')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-4', {'balance': 1000})
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-4', 'synchronizationId2')
        assert 'vint-hill:1:ps-mpa-1' in state._state_by_instance_index
        assert 'vint-hill:1:ps-mpa-2' not in state._state_by_instance_index
        assert 'vint-hill:2:ps-mpa-3' in state._state_by_instance_index

    @pytest.mark.asyncio
    async def test_delete_state_on_disconnected_if_there_is_another_synced_state(self):
        """Should delete state on disconnected if there is another synced state."""
        terminal_hash_manager.remove_connection_references = MagicMock()
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-1', 1)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-1', 'synchronizationId2')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-2', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-2', 1)
        await state.on_pending_orders_synchronized('vint-hill:1:ps-mpa-2', 'synchronizationId2')
        await state.on_stream_closed('vint-hill:1:ps-mpa-2')
        terminal_hash_manager.remove_connection_references.assert_called_with(state.id, 'vint-hill:1:ps-mpa-2')
        assert 'vint-hill:1:ps-mpa-1' in state._state_by_instance_index
        assert 'vint-hill:1:ps-mpa-2' not in state._state_by_instance_index

    @pytest.mark.asyncio
    async def test_delete_partially_synced_state_on_disconnected_if_there_is_fresher_state(self):
        """Should delete partially synced state on disconnected if there is another fresher state."""
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-1', 1)
        await state.on_account_information_updated('vint-hill:1:ps-mpa-2', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-2', 1)
        await state.on_stream_closed('vint-hill:1:ps-mpa-1')
        assert 'vint-hill:1:ps-mpa-1' not in state._state_by_instance_index
        assert 'vint-hill:1:ps-mpa-2' in state._state_by_instance_index

    @pytest.mark.asyncio
    async def test_not_delete_partially_synced_state_on_disconnected_if_there_is_no_fresher_state(self):
        """Should not delete partially synced state on disconnected if there is no fresher state."""
        await state.on_synchronization_started('vint-hill:1:ps-mpa-1', 'shash1', 'phash1', 'ohash1')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-1', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-1', 1)
        await asyncio.sleep(0.1)
        await state.on_synchronization_started('vint-hill:1:ps-mpa-2', 'shash1', 'phash1', 'ohash1')
        await state.on_account_information_updated('vint-hill:1:ps-mpa-2', {'balance': 1000})
        await state.on_connected('vint-hill:1:ps-mpa-2', 1)
        await state.on_disconnected('vint-hill:1:ps-mpa-2')
        assert 'vint-hill:1:ps-mpa-1' in state._state_by_instance_index
        assert 'vint-hill:1:ps-mpa-2' in state._state_by_instance_index


class TestRefreshTerminalState:
    @pytest.mark.asyncio
    async def test_initiate_refreshing_terminal_state_and_wait_for_all_refreshed_prices_received(self):
        """Should initiate refreshing terminal state and wait for all refreshed prices received."""
        websocket_client.refresh_terminal_state = AsyncMock(return_value=['EURUSD', 'BTCUSD'])

        task = asyncio.create_task(state.refresh_terminal_state())

        asyncio.create_task(state.on_symbol_prices_updated('0', [{'symbol': 'EURUSD'}]))
        await sleep(0.000005)
        assert not task.done()

        asyncio.create_task(state.on_symbol_prices_updated('0', [{'symbol': 'BTCUSD'}]))

        await task

    @pytest.mark.asyncio
    async def test_time_out_waiting_refreshed_prices_receival(self):
        """Should time out waiting refreshed prices receival."""

        websocket_client.refresh_terminal_state = AsyncMock(return_value=['EURUSD', 'BTCUSD'])

        promise = asyncio.create_task(state.refresh_terminal_state({'timeoutInSeconds': 0.01}))
        asyncio.create_task(state.on_symbol_prices_updated('0', [{'symbol': 'EURUSD'}]))

        try:
            await promise
            raise Exception('assert')
        except Exception as err:
            assert isinstance(err, TimeoutException)

    @pytest.mark.asyncio
    async def test_not_raise_unhandled_rejection_if_ws_request_fails_after_waiting_prices_timed_out(self):
        """Should not raise unhandled rejection if ws request fails after waiting prices timed out."""

        async def refresh_terminal_state(options):
            await sleep(0.0001)
            raise Exception('test')

        websocket_client.refresh_terminal_state = AsyncMock(side_effect=refresh_terminal_state)

        try:
            await state.refresh_terminal_state({'timeoutInSeconds': 0.001})
            raise Exception('assert')
        except Exception as err:
            assert isinstance(err, TimeoutException)
            websocket_client.refresh_terminal_state.assert_called_once()
            await sleep(0.000015)

    @pytest.mark.asyncio
    async def test_not_wait_for_any_symbols_if_no_symbols_initiated_to_refresh(self):
        """Should not wait for any symbols if no symbols initiated to refresh."""
        websocket_client.refresh_terminal_state = AsyncMock(return_value=[])
        await state.refresh_terminal_state()
        websocket_client.refresh_terminal_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_wait_for_symbols_if_they_already_received_before_refresh_call_completed(self):
        """Should not wait for symbols if they were already received before refresh call completed."""

        async def refresh_terminal_state(options):
            asyncio.create_task(state.on_symbol_prices_updated('0', [{'symbol': 'EURUSD'}, {'symbol': 'BTCUSD'}]))

            return ['EURUSD', 'BTCUSD']

        websocket_client.refresh_terminal_state = AsyncMock(side_effect=refresh_terminal_state)
        await state.refresh_terminal_state()

        websocket_client.refresh_terminal_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_conflict_when_waiting_for_different_call_resolving(self):
        """Should not conflict when waiting for different call resolving."""
        websocket_client.refresh_terminal_state = AsyncMock(side_effect=[['EURUSD', 'BTCUSD'], ['EURUSD', 'AUDUSD']])

        task_1 = asyncio.create_task(state.refresh_terminal_state())
        await sleep(0.000005)
        task_2 = asyncio.create_task(state.refresh_terminal_state())
        await sleep(0.000005)

        asyncio.create_task(
            state.on_symbol_prices_updated('0', [{'symbol': 'EURUSD'}, {'symbol': 'BTCUSD'}, {'symbol': 'AUDUSD'}])
        )
        await task_1
        await task_2

        assert websocket_client.refresh_terminal_state.call_count == 2
