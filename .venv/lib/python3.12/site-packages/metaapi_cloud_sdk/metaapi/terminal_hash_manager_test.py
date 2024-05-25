from asyncio import sleep
from hashlib import md5

import pytest
from freezegun import freeze_time
from mock.mock import MagicMock, patch

from lib.clients.metaapi.client_api_client import ClientApiClient, HashingIgnoredFieldLists
from .models import date
from .terminal_hash_manager import TerminalHashManager

client_api_client: ClientApiClient = None
terminal_hash_manager: TerminalHashManager = None
ignored_field_lists: HashingIgnoredFieldLists = None


class MockClientApiClient(ClientApiClient):
    async def refresh_ignored_field_lists(self, region):
        pass

    def get_hashing_ignored_field_lists(self, region: str) -> HashingIgnoredFieldLists:
        pass


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch('lib.metaapi.reference_tree.asyncio.sleep', new=lambda x: sleep(x / 1000)):
        global ignored_field_lists
        ignored_field_lists = {
            'g1': {
                'specification': [
                    'description',
                    'expirationTime',
                    'expirationBrokerTime',
                    'startTime',
                    'startBrokerTime',
                    'pipSize',
                ],
                'position': [
                    'time',
                    'updateTime',
                    'comment',
                    'brokerComment',
                    'originalComment',
                    'clientId',
                    'profit',
                    'realizedProfit',
                    'unrealizedProfit',
                    'currentPrice',
                    'currentTickValue',
                    'accountCurrencyExchangeRate',
                    'updateSequenceNumber',
                ],
                'order': [
                    'time',
                    'expirationTime',
                    'comment',
                    'brokerComment',
                    'originalComment',
                    'clientId',
                    'currentPrice',
                    'accountCurrencyExchangeRate',
                    'updateSequenceNumber',
                ],
            },
            'g2': {
                'specification': ['pipSize'],
                'position': [
                    'comment',
                    'brokerComment',
                    'originalComment',
                    'clientId',
                    'profit',
                    'realizedProfit',
                    'unrealizedProfit',
                    'currentPrice',
                    'currentTickValue',
                    'accountCurrencyExchangeRate',
                    'updateSequenceNumber',
                ],
                'order': [
                    'comment',
                    'brokerComment',
                    'originalComment',
                    'clientId',
                    'currentPrice',
                    'accountCurrencyExchangeRate',
                    'updateSequenceNumber',
                ],
            },
        }
        global client_api_client
        client_api_client = MockClientApiClient(MagicMock(), MagicMock())
        client_api_client.get_hashing_ignored_field_lists = MagicMock(return_value=ignored_field_lists)
        global terminal_hash_manager
        terminal_hash_manager = TerminalHashManager(client_api_client)
        yield


class TestTerminalHashManager:
    @pytest.mark.asyncio
    async def test_record_specification_hash(self):
        """Record specification hash."""
        specifications = [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}]
        terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', specifications
        )
        popular_hashes = terminal_hash_manager.get_last_used_specification_hashes('ICMarkets-Demo02')
        assert popular_hashes == ['8908db669eed0b715ab3559300846b3b']

    @pytest.mark.asyncio
    async def test_record_and_return_specification(self):
        """Record and return specifications."""
        specifications = [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}]
        hash = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', specifications
        )
        data = terminal_hash_manager.get_specifications_by_hash(hash)
        assert data == {'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001}, 'GBPUSD': {'symbol': 'GBPUSD'}}
        updated_hash = terminal_hash_manager.update_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'AUDUSD', 'tickSize': 0.001}, {'symbol': 'BTCUSD'}],
            ['GBPUSD'],
            hash,
        )
        updated_data = terminal_hash_manager.get_specifications_by_hash(updated_hash)
        assert updated_data == {
            'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001},
            'AUDUSD': {'symbol': 'AUDUSD', 'tickSize': 0.001},
            'BTCUSD': {'symbol': 'BTCUSD'},
        }
        updated_hash_2 = terminal_hash_manager.update_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'CADUSD', 'tickSize': 0.001}],
            ['BTCUSD'],
            updated_hash,
        )
        updated_data_2 = terminal_hash_manager.get_specifications_by_hash(updated_hash_2)
        assert updated_data_2 == {
            'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001},
            'AUDUSD': {'symbol': 'AUDUSD', 'tickSize': 0.001},
            'CADUSD': {'symbol': 'CADUSD', 'tickSize': 0.001},
        }

    @pytest.mark.asyncio
    async def test_update_specification_to_correct_hash(self):
        """Should update specifications to correct hash."""
        hash_1 = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.001}],
        )
        updated_hash = terminal_hash_manager.update_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'AUDUSD', 'tickSize': 0.001}, {'symbol': 'BTCUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.002}],
            ['GBPUSD'],
            hash_1,
        )
        hash_2 = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [
                {'symbol': 'EURUSD', 'tickSize': 0.0001},
                {'symbol': 'AUDUSD', 'tickSize': 0.001},
                {'symbol': 'BTCUSD'},
                {'symbol': 'CADUSD', 'tickSize': 0.002},
            ],
        )
        assert updated_hash == hash_2

    @pytest.mark.asyncio
    async def test_clean_up_unused_entry_with_no_children(self):
        """Should clean up unused entry that has no children."""
        with freeze_time() as frozen_datetime:
            hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.001},
                ],
            )
            terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD'}],
            )
            terminal_hash_manager.get_specifications_by_hash(hash)
            frozen_datetime.tick(960)
            await sleep(0.96)
            specifications = terminal_hash_manager.get_specifications_by_hash(hash)
            assert specifications is None

    @pytest.mark.asyncio
    async def test_clean_up_unused_entry_with_one_child(self):
        """Should clean up unused entry with one child."""
        with freeze_time() as frozen_datetime:
            hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.001},
                ],
            )
            hash_2 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [
                    {'symbol': 'AUDUSD', 'tickSize': 0.001},
                    {'symbol': 'BTCUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.002},
                ],
                ['GBPUSD'],
                hash,
            )
            terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD'}],
            )
            terminal_hash_manager.get_specifications_by_hash(hash)
            frozen_datetime.tick(960)
            await sleep(0.96)
            specifications = terminal_hash_manager.get_specifications_by_hash(hash)
            assert specifications is None

            specifications_2 = terminal_hash_manager.get_specifications_by_hash(hash_2)

            assert specifications_2 == {
                'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001},
                'CADUSD': {'symbol': 'CADUSD', 'tickSize': 0.002},
                'AUDUSD': {'symbol': 'AUDUSD', 'tickSize': 0.001},
                'BTCUSD': {'symbol': 'BTCUSD'},
            }

    @pytest.mark.asyncio
    async def test_combine_child_entry_with_parent_entry(self):
        """Should combine child entry with parent entry with multiple steps."""
        with freeze_time() as frozen_datetime:
            hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.001},
                ],
            )
            hash_2 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [
                    {'symbol': 'AUDUSD', 'tickSize': 0.001},
                    {'symbol': 'BTCUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.002},
                ],
                ['GBPUSD'],
                hash,
            )
            hash_3 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [{'symbol': 'AUDUSD', 'tickSize': 0.003}],
                [],
                hash_2,
            )
            hash_4 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [{'symbol': 'AUDUSD', 'tickSize': 0.004}],
                [],
                hash_3,
            )
            hash_5 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [{'symbol': 'AUDUSD', 'tickSize': 0.005}],
                [],
                hash_4,
            )
            specifications = terminal_hash_manager.get_specifications_by_hash(hash_5)
            terminal_hash_manager.add_specification_reference(hash_2, 'connectionId', 'vint-hill:1:ps-mpa-1')

            assert specifications == {
                'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001},
                'CADUSD': {'symbol': 'CADUSD', 'tickSize': 0.002},
                'AUDUSD': {'symbol': 'AUDUSD', 'tickSize': 0.005},
                'BTCUSD': {'symbol': 'BTCUSD'},
            }

            frozen_datetime.tick(960)
            await sleep(0.96)

            specifications_2 = terminal_hash_manager.get_specifications_by_hash(hash_5)

            assert specifications == specifications_2

    @pytest.mark.asyncio
    async def test_no_clean_up_unused_entry_with_multiple_children(self):
        """Should not clean up unused entry with multiple children."""
        hash = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.001}],
        )
        terminal_hash_manager.update_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-2',
            [{'symbol': 'AUDUSD', 'tickSize': 0.001}, {'symbol': 'BTCUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.002}],
            ['GBPUSD'],
            hash,
        )
        terminal_hash_manager.update_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-3',
            [{'symbol': 'AUDUSD', 'tickSize': 0.001}, {'symbol': 'BTCUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.003}],
            ['GBPUSD'],
            hash,
        )
        terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD'}],
        )
        terminal_hash_manager.get_specifications_by_hash(hash)
        await sleep(0.96)
        terminal_hash_manager.get_specifications_by_hash(hash)

    @pytest.mark.asyncio
    async def test_combine_changes_if_child_and_parent_exist(self):
        """Should combine changes if both child and parent exist."""
        with freeze_time() as frozen_datetime:
            hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.001},
                ],
            )
            hash_2 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [
                    {'symbol': 'AUDUSD', 'tickSize': 0.001},
                    {'symbol': 'ETHUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.002},
                ],
                ['GBPUSD'],
                hash,
            )
            hash_3 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [{'symbol': 'BTCUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.003}],
                ['AUDUSD'],
                hash_2,
            )
            data_1 = terminal_hash_manager.get_specifications_by_hash(hash_3)
            frozen_datetime.tick(960)
            await sleep(0.96)
            specifications = terminal_hash_manager.get_specifications_by_hash(hash_2)
            assert specifications is None
            data_2 = terminal_hash_manager.get_specifications_by_hash(hash_3)
            assert data_1 == data_2

    @pytest.mark.asyncio
    async def test_reassign_child_hash_to_parent_if_object_between_is_removed(self):
        """Should reassign child hash to parent if object between is removed."""
        with freeze_time() as frozen_datetime:
            hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.001},
                ],
            )
            hash_2 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [
                    {'symbol': 'AUDUSD', 'tickSize': 0.001},
                    {'symbol': 'ETHUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.002},
                ],
                ['GBPUSD'],
                hash,
            )
            hash_3 = terminal_hash_manager.update_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-2',
                [{'symbol': 'BTCUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.003}],
                ['AUDUSD'],
                hash_2,
            )
            data_1 = terminal_hash_manager.get_specifications_by_hash(hash_3)
            frozen_datetime.tick(960)
            await sleep(0.96)
            specifications_2 = terminal_hash_manager.get_specifications_by_hash(hash_2)
            assert specifications_2 is None

            terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [
                    {'symbol': 'EURUSD', 'tickSize': 0.0001},
                    {'symbol': 'GBPUSD'},
                    {'symbol': 'CADUSD', 'tickSize': 0.005},
                ],
            )
            data_2 = terminal_hash_manager.get_specifications_by_hash(hash_3)

            assert data_1 == data_2

    @pytest.mark.asyncio
    async def test_get_last_used_position_hashes_with_fuzzy_search(self):
        """Should get last used specifications hashes with fuzzy search."""
        hash = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.001}],
        )
        await sleep(0.0005)
        hash_2 = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'CADUSD', 'tickSize': 0.001}],
        )
        await sleep(0.0005)
        hash_3 = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo01',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'GBPUSD'}, {'symbol': 'CADUSD', 'tickSize': 0.001}],
        )
        await sleep(0.0005)
        hash_4 = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo01',
            'cloud-g1',
            'connectionId',
            'vint-hill:1:ps-mpa-1',
            [{'symbol': 'EURUSD', 'tickSize': 0.0001}, {'symbol': 'GBPUSD'}],
        )
        await sleep(0.0005)
        terminal_hash_manager.record_specifications(
            'VantageFX', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [{'symbol': 'CADUSD', 'tickSize': 0.001}]
        )
        last_used_hashes = terminal_hash_manager.get_last_used_specification_hashes('ICMarkets-Demo02')
        assert last_used_hashes == [hash_2, hash, hash_4, hash_3]

    @pytest.mark.asyncio
    async def test_record_position_and_return_by_hash(self):
        """Should record positions and return by hash."""
        positions = [{'id': '1', 'volume': 10}, {'id': '2', 'volume': 20}]
        expected_hashes = ['f915d7e4b04a30a96fe6cf770a38fedb', 'c472cdc6239536770a7279af01fc10a7']
        hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )

        recorded_positions = terminal_hash_manager.get_positions_by_hash(hash)
        hashes = terminal_hash_manager.get_positions_hashes_by_hash(hash)
        assert recorded_positions == {'1': positions[0], '2': positions[1]}
        assert hashes['1'] == expected_hashes[0]
        assert hashes['2'] == expected_hashes[1]

    @pytest.mark.asyncio
    async def test_update_positions(self):
        """Should update positions."""
        positions = [{'id': '1', 'volume': 10}, {'id': '2', 'volume': 20}, {'id': '3', 'volume': 30}]
        hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )
        new_positions = [{'id': '1', 'volume': 30}]
        updated_hash = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', new_positions, [], hash
        )
        recorded_positions = terminal_hash_manager.get_positions_by_hash(updated_hash)
        assert recorded_positions == {'1': new_positions[0], '2': positions[1], '3': positions[2]}
        hashes = terminal_hash_manager.get_positions_hashes_by_hash(updated_hash)
        assert hashes == {
            '1': terminal_hash_manager.get_item_hash(new_positions[0], 'positions', 'cloud-g1', 'vint-hill'),
            '2': terminal_hash_manager.get_item_hash(positions[1], 'positions', 'cloud-g1', 'vint-hill'),
            '3': terminal_hash_manager.get_item_hash(positions[2], 'positions', 'cloud-g1', 'vint-hill'),
        }
        new_positions_2 = [{'id': '3', 'volume': 50}]
        updated_hash_2 = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', new_positions_2, [], updated_hash
        )
        recorded_positions_2 = terminal_hash_manager.get_positions_by_hash(updated_hash_2)
        assert recorded_positions_2 == {'1': new_positions[0], '2': positions[1], '3': new_positions_2[0]}
        hashes_2 = terminal_hash_manager.get_positions_hashes_by_hash(updated_hash_2)
        assert hashes_2 == {
            '1': terminal_hash_manager.get_item_hash(new_positions[0], 'positions', 'cloud-g1', 'vint-hill'),
            '2': terminal_hash_manager.get_item_hash(positions[1], 'positions', 'cloud-g1', 'vint-hill'),
            '3': terminal_hash_manager.get_item_hash(new_positions_2[0], 'positions', 'cloud-g1', 'vint-hill'),
        }

    @pytest.mark.asyncio
    async def test_remove_positions(self):
        """Should remove positions."""
        positions = [
            {'id': '1', 'volume': 10},
            {'id': '2', 'volume': 20},
            {'id': '3', 'volume': 30},
            {'id': '4', 'volume': 40},
        ]
        hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )
        await sleep(0.0005)
        updated_hash = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], hash
        )
        recorded_positions = terminal_hash_manager.get_positions_by_hash(updated_hash)
        assert recorded_positions == {'1': positions[0], '3': positions[2], '4': positions[3]}
        await sleep(0.0005)
        updated_hash_2 = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], updated_hash
        )
        recorded_positions_2 = terminal_hash_manager.get_positions_by_hash(updated_hash_2)
        assert updated_hash == updated_hash_2
        assert {'1': positions[0], '3': positions[2], '4': positions[3]} == recorded_positions_2
        await sleep(0.0005)
        updated_hash_3 = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3'], updated_hash_2
        )
        recorded_positions_3 = terminal_hash_manager.get_positions_by_hash(updated_hash_3)
        assert {'1': positions[0], '4': positions[3]} == recorded_positions_3
        updated_hash_4 = terminal_hash_manager.update_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3', '4'], updated_hash_3
        )
        recorded_positions_4 = terminal_hash_manager.get_positions_by_hash(updated_hash_4)
        assert {'1': positions[0]} == recorded_positions_4

    @pytest.mark.asyncio
    async def test_optimize_position_trees(self):
        """Should optimize position trees."""
        with freeze_time() as frozen_datetime:
            positions = [
                {'id': '1', 'volume': 10},
                {'id': '2', 'volume': 20},
                {'id': '3', 'volume': 30},
                {'id': '4', 'volume': 40},
            ]
            hash = terminal_hash_manager.record_positions(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
            )
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash = terminal_hash_manager.update_positions(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '4'], hash
            )
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash_2 = terminal_hash_manager.update_positions(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '3'], updated_hash
            )
            recorded_positions = terminal_hash_manager.get_positions_by_hash(updated_hash_2)
            assert recorded_positions == {'1': positions[0]}
            frozen_datetime.tick(550)
            await sleep(0.55)
            recorded_positions_2 = terminal_hash_manager.get_positions_by_hash(updated_hash_2)
            assert {'1': positions[0]} == recorded_positions_2

    @pytest.mark.asyncio
    async def test_get_last_used_position_hashes(self):
        """Should get last used positions hashes."""
        positions = [
            {'id': '1', 'volume': 10},
            {'id': '2', 'volume': 20},
            {'id': '3', 'volume': 30},
            {'id': '4', 'volume': 40},
        ]
        hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )
        await sleep(0.0005)
        terminal_hash_manager.record_positions(
            'accountId2', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [positions[0]]
        )
        await sleep(0.0005)
        hash_3 = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [positions[1]]
        )
        last_used_hashes = terminal_hash_manager.get_last_used_position_hashes('accountId')
        assert last_used_hashes == [hash_3, hash]

    @pytest.mark.asyncio
    async def test_record_orders_and_return_by_hash(self):
        """Should record orders and return by hash."""
        orders = [{'id': '1', 'openPrice': 10}, {'id': '2', 'openPrice': 20}]
        expected_hashes = ['df061bbdcae2ec5f7feec06edeed170e', 'a4766bbdb57dc4629bb0d0eede270c5f']
        hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )

        recorded_orders = terminal_hash_manager.get_orders_by_hash(hash)
        hashes = terminal_hash_manager.get_orders_hashes_by_hash(hash)
        assert recorded_orders == {'1': orders[0], '2': orders[1]}
        assert expected_hashes[0] == hashes['1']
        assert expected_hashes[1] == hashes['2']

    @pytest.mark.asyncio
    async def test_update_orders(self):
        """Should update orders."""
        orders = [{'id': '1', 'openPrice': 10}, {'id': '2', 'openPrice': 20}, {'id': '3', 'openPrice': 30}]
        hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )
        new_orders = [{'id': '1', 'openPrice': 30}]
        updated_hash = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', new_orders, [], hash
        )
        recorded_orders = terminal_hash_manager.get_orders_by_hash(updated_hash)
        assert recorded_orders == {'1': new_orders[0], '2': orders[1], '3': orders[2]}
        hashes = terminal_hash_manager.get_orders_hashes_by_hash(updated_hash)
        assert hashes == {
            '1': terminal_hash_manager.get_item_hash(new_orders[0], 'orders', 'cloud-g1', 'vint-hill'),
            '2': terminal_hash_manager.get_item_hash(orders[1], 'orders', 'cloud-g1', 'vint-hill'),
            '3': terminal_hash_manager.get_item_hash(orders[2], 'orders', 'cloud-g1', 'vint-hill'),
        }
        new_orders_2 = [{'id': '3', 'openPrice': 50}]
        updated_hash_2 = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', new_orders_2, [], updated_hash
        )
        recorded_orders_2 = terminal_hash_manager.get_orders_by_hash(updated_hash_2)
        assert recorded_orders_2 == {'1': new_orders[0], '2': orders[1], '3': new_orders_2[0]}
        hashes_2 = terminal_hash_manager.get_orders_hashes_by_hash(updated_hash_2)
        assert hashes_2 == {
            '1': terminal_hash_manager.get_item_hash(new_orders[0], 'orders', 'cloud-g1', 'vint-hill'),
            '2': terminal_hash_manager.get_item_hash(orders[1], 'orders', 'cloud-g1', 'vint-hill'),
            '3': terminal_hash_manager.get_item_hash(new_orders_2[0], 'orders', 'cloud-g1', 'vint-hill'),
        }

    @pytest.mark.asyncio
    async def test_remove_orders(self):
        """Should remove orders."""
        orders = [
            {'id': '1', 'openPrice': 10},
            {'id': '2', 'openPrice': 20},
            {'id': '3', 'openPrice': 30},
            {'id': '4', 'openPrice': 40},
        ]
        hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )
        await sleep(0.0005)
        updated_hash = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], hash
        )
        recorded_orders = terminal_hash_manager.get_orders_by_hash(updated_hash)
        assert recorded_orders == {'1': orders[0], '3': orders[2], '4': orders[3]}
        await sleep(0.0005)
        updated_hash_2 = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], updated_hash
        )
        recorded_orders_2 = terminal_hash_manager.get_orders_by_hash(updated_hash_2)
        assert updated_hash == updated_hash_2
        assert recorded_orders_2 == {'1': orders[0], '3': orders[2], '4': orders[3]}
        await sleep(0.0005)
        updated_hash_3 = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3'], updated_hash_2
        )
        recorded_orders_3 = terminal_hash_manager.get_orders_by_hash(updated_hash_3)
        assert recorded_orders_3 == {'1': orders[0], '4': orders[3]}
        await sleep(0.0005)
        updated_hash_4 = terminal_hash_manager.update_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3', '4'], updated_hash_3
        )
        recorded_orders_4 = terminal_hash_manager.get_orders_by_hash(updated_hash_4)
        assert recorded_orders_4 == {'1': orders[0]}

    @pytest.mark.asyncio
    async def test_optimize_order_trees(self):
        """Should optimize order trees."""
        with freeze_time() as frozen_datetime:
            orders = [
                {'id': '1', 'openPrice': 10},
                {'id': '2', 'openPrice': 20},
                {'id': '3', 'openPrice': 30},
                {'id': '4', 'openPrice': 40},
            ]
            hash = terminal_hash_manager.record_orders(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
            )
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash = terminal_hash_manager.update_orders(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '4'], hash
            )
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash_2 = terminal_hash_manager.update_orders(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '3'], updated_hash
            )
            recorded_orders = terminal_hash_manager.get_orders_by_hash(updated_hash_2)
            assert recorded_orders == {'1': orders[0]}
            frozen_datetime.tick(550)
            await sleep(0.55)
            recorded_orders_2 = terminal_hash_manager.get_orders_by_hash(updated_hash_2)
            assert recorded_orders_2 == {'1': orders[0]}

    @pytest.mark.asyncio
    async def test_get_last_used_order_hashes(self):
        """Should get last used orders hashes."""
        orders = [
            {'id': '1', 'openPrice': 10},
            {'id': '2', 'openPrice': 20},
            {'id': '3', 'openPrice': 30},
            {'id': '4', 'openPrice': 40},
        ]
        hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )
        await sleep(0.0005)
        terminal_hash_manager.record_orders(
            'accountId2', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [orders[0]]
        )
        await sleep(0.0005)
        hash_3 = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [orders[1]]
        )
        last_used_hashes = terminal_hash_manager.get_last_used_order_hashes('accountId')
        assert last_used_hashes == [hash_3, hash]

    @pytest.mark.asyncio
    async def test_remove_connection_references(self):
        """Should remove connection references."""
        with freeze_time() as frozen_datetime:
            specifications = [{'symbol': 'EURUSD', 'tickSize': 0.0001}]
            positions = [{'id': '1', 'volume': 10}]
            orders = [{'id': '1', 'openPrice': 10}]
            specifications_hash = terminal_hash_manager.record_specifications(
                'ICMarkets-Demo02', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', specifications
            )
            positions_hash = terminal_hash_manager.record_positions(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
            )
            orders_hash = terminal_hash_manager.record_orders(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
            )
            frozen_datetime.tick(960)
            await sleep(0.96)
            specs_data = terminal_hash_manager.get_specifications_by_hash(specifications_hash)
            assert specs_data == {'EURUSD': {'symbol': 'EURUSD', 'tickSize': 0.0001}}

            positions_data = terminal_hash_manager.get_positions_by_hash(positions_hash)
            assert positions_data == {'1': {'id': '1', 'volume': 10}}

            orders_data = terminal_hash_manager.get_orders_by_hash(orders_hash)
            assert orders_data == {'1': {'id': '1', 'openPrice': 10}}
            terminal_hash_manager.remove_connection_references('connectionId', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(960)
            await sleep(0.96)

            specs_data_2 = terminal_hash_manager.get_specifications_by_hash(specifications_hash)
            assert specs_data_2 is None

            positions_data_2 = terminal_hash_manager.get_positions_by_hash(positions_hash)
            assert positions_data_2 is None

            orders_data_2 = terminal_hash_manager.get_orders_by_hash(orders_hash)
            assert orders_data_2 is None

    @pytest.mark.asyncio
    async def test_return_hashes_for_cloud_g1_accounts(self):
        """Should return hashes for cloud-g1 accounts."""
        expected_specifications_hash = [
            md5('{"symbol":"AUDNZD","tickSize":0.01000000}'.encode()).hexdigest(),
            md5(
                (
                    '{"symbol":"EURUSD","tickSize":0.00000100,"contractSize":1.00000000,"maxVolume":30000.00000000,'
                    '"hedgedMarginUsesLargerLeg":false,"digits":3}'
                ).encode()
            ).hexdigest(),
        ]
        expected_positions_hash = md5(
            (
                '{"id":"46214692","type":"POSITION_TYPE_BUY","symbol":"GBPUSD","magic":1000,'
                '"openPrice":1.26101000,"volume":0.07000000,"swap":0.00000000,"commission":-0.25000000,'
                '"stopLoss":1.17721000}'
            ).encode()
        ).hexdigest()
        expected_orders_hash = md5(
            (
                '{"id":"46871284","type":"ORDER_TYPE_BUY_LIMIT","state":"ORDER_STATE_PLACED",'
                '"symbol":"AUDNZD","magic":123456,"platform":"mt5","openPrice":1.03000000,'
                '"volume":0.01000000,"currentVolume":0.01000000}'
            ).encode()
        ).hexdigest()
        specifications = [
            {'symbol': 'AUDNZD', 'tickSize': 0.01, 'description': 'Test1'},
            {
                'symbol': 'EURUSD',
                'tickSize': 0.000001,
                'contractSize': 1,
                'maxVolume': 30000,
                'hedgedMarginUsesLargerLeg': False,
                'digits': 3,
                'description': 'Test2',
            },
        ]
        specifications_hash = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', specifications
        )
        result_specifications_hashes = terminal_hash_manager.get_specifications_hashes_by_hash(specifications_hash)
        assert result_specifications_hashes.get('AUDNZD') == expected_specifications_hash[0]
        assert result_specifications_hashes.get('EURUSD') == expected_specifications_hash[1]

        positions = [
            {
                'id': '46214692',
                'type': 'POSITION_TYPE_BUY',
                'symbol': 'GBPUSD',
                'magic': 1000,
                'time': date('2020-04-15T02:45:06.521Z'),
                'updateTime': date('2020-04-15T02:45:06.521Z'),
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
                'updateSequenceNumber': 13246,
                'accountCurrencyExchangeRate': 1,
                'comment': 'test',
                'brokerComment': 'test2',
            }
        ]
        positions_hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )
        assert positions_hash == expected_positions_hash
        orders = [
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
                'volume': 0.01,
                'currentVolume': 0.01,
                'comment': 'COMMENT2',
                'updateSequenceNumber': 13246,
                'accountCurrencyExchangeRate': 1,
                'brokerComment': 'test2',
                'clientId': 'TE_GBPUSD_7hyINWqAlE',
            }
        ]
        orders_hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )
        assert orders_hash == expected_orders_hash

    @pytest.mark.asyncio
    async def test_return_hashes_for_cloud_g2_accounts(self):
        """Should return hashes for cloud-g2 accounts."""
        expected_specifications_hash = [
            md5('{"symbol":"AUDNZD","tickSize":0.01,"description":"Test1"}'.encode()).hexdigest(),
            md5(
                (
                    '{"symbol":"EURUSD","tickSize":0.000001,"contractSize":1,"maxVolume":30000,'
                    '"hedgedMarginUsesLargerLeg":false,"digits":3,"description":"Test2"}'
                ).encode()
            ).hexdigest(),
        ]
        expected_positions_hash = md5(
            (
                '{"id":"46214692","type":"POSITION_TYPE_BUY","symbol":"GBPUSD","magic":1000,'
                '"time":"2020-04-15T02:45:06.521Z","updateTime":"2020-04-15T02:45:06.521Z","openPrice":1.26101,'
                '"volume":0.07,"swap":0,"commission":-0.25,"stopLoss":1.17721}'
            ).encode()
        ).hexdigest()
        expected_orders_hash = md5(
            (
                '{"id":"46871284","type":"ORDER_TYPE_BUY_LIMIT","state":"ORDER_STATE_PLACED",'
                '"symbol":"AUDNZD","magic":123456,"platform":"mt5","time":"2020-04-20T08:38:58.270Z",'
                '"openPrice":1.03,"volume":0.01,"currentVolume":0.01}'
            ).encode()
        ).hexdigest()
        specifications = [
            {'symbol': 'AUDNZD', 'tickSize': 0.01, 'description': 'Test1'},
            {
                'symbol': 'EURUSD',
                'tickSize': 0.000001,
                'contractSize': 1,
                'maxVolume': 30000,
                'hedgedMarginUsesLargerLeg': False,
                'digits': 3,
                'description': 'Test2',
            },
        ]
        specifications_hash = terminal_hash_manager.record_specifications(
            'ICMarkets-Demo02', 'cloud-g2', 'connectionId', 'vint-hill:1:ps-mpa-1', specifications
        )
        result_specifications_hashes = terminal_hash_manager.get_specifications_hashes_by_hash(specifications_hash)
        assert result_specifications_hashes.get('AUDNZD') == expected_specifications_hash[0]
        assert result_specifications_hashes.get('EURUSD') == expected_specifications_hash[1]

        positions = [
            {
                'id': '46214692',
                'type': 'POSITION_TYPE_BUY',
                'symbol': 'GBPUSD',
                'magic': 1000,
                'time': date('2020-04-15T02:45:06.521Z'),
                'updateTime': date('2020-04-15T02:45:06.521Z'),
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
                'updateSequenceNumber': 13246,
                'accountCurrencyExchangeRate': 1,
                'comment': 'test',
                'brokerComment': 'test2',
            }
        ]
        positions_hash = terminal_hash_manager.record_positions(
            'accountId', 'cloud-g2', 'connectionId', 'vint-hill:1:ps-mpa-1', positions
        )
        assert positions_hash == expected_positions_hash

        orders = [
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
                'volume': 0.01,
                'currentVolume': 0.01,
                'comment': 'COMMENT2',
                'updateSequenceNumber': 13246,
                'accountCurrencyExchangeRate': 1,
                'brokerComment': 'test2',
                'clientId': 'TE_GBPUSD_7hyINWqAlE',
            }
        ]

        orders_hash = terminal_hash_manager.record_orders(
            'accountId', 'cloud-g2', 'connectionId', 'vint-hill:1:ps-mpa-1', orders
        )
        assert orders_hash == expected_orders_hash
