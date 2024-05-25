from asyncio import sleep

import pytest
from freezegun import freeze_time
from mock.mock import patch, MagicMock

from lib.clients.metaapi.client_api_client import ClientApiClient, HashingIgnoredFieldLists
from lib.metaapi.reference_tree import ReferenceTree
from lib.metaapi.terminal_hash_manager import TerminalHashManager

terminal_hash_manager: TerminalHashManager = None
tree: ReferenceTree = None
fuzzy_tree: ReferenceTree = None


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


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch("lib.metaapi.reference_tree.asyncio.sleep", new=lambda x: sleep(x / 1000)):
        client_api_client = MockClientApiClient(MagicMock(), MagicMock())
        global terminal_hash_manager
        terminal_hash_manager = TerminalHashManager(client_api_client)
        global tree
        tree = ReferenceTree(terminal_hash_manager, "id", "positions")
        global fuzzy_tree
        fuzzy_tree = ReferenceTree(terminal_hash_manager, "symbol", "specifications", True)
        yield


class TestReferenceTree:
    @pytest.mark.asyncio
    async def test_record_data(self):
        """Should record data."""
        data = [{"id": "1", "volume": 10}, {"id": "2", "volume": 20}]
        nodata = tree.get_items_by_hash("test")
        assert nodata is None
        nohash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [])
        assert nohash is None
        hash = tree.record_items("accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", data)
        nodata_2 = tree.get_items_by_hash("test2")
        assert nodata_2 is None
        expected_hashes = ["f915d7e4b04a30a96fe6cf770a38fedb", "c472cdc6239536770a7279af01fc10a7"]
        items = tree.get_items_by_hash(hash)
        assert items == {"1": data[0], "2": data[1]}
        hashes = tree.get_hashes_by_hash(hash)
        assert hashes["1"] == expected_hashes[0]
        assert hashes["2"] == expected_hashes[1]

    @pytest.mark.asyncio
    async def test_add_reference_if_same_data_recorded_twice(self):
        """Should add reference if same data recorded twice."""
        data = [{'id': '1', 'volume': 10}, {'id': '2', 'volume': 20}]
        hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', data)
        hash_2 = tree.record_items('accountId2', 'cloud-g1', 'connectionId2', 'vint-hill:1:ps-mpa-1', data)
        expected_hashes = ['f915d7e4b04a30a96fe6cf770a38fedb', 'c472cdc6239536770a7279af01fc10a7']
        items = tree.get_items_by_hash(hash)

        assert items == {'1': data[0], '2': data[1]}

        hashes = tree.get_hashes_by_hash(hash)

        assert hashes['1'] == expected_hashes[0]
        assert hashes['2'] == expected_hashes[1]
        assert hash == hash_2

    @pytest.mark.asyncio
    async def test_update_data(self):
        """Should update data."""
        items = [{"id": "1", "volume": 10}, {"id": "2", "volume": 20}, {"id": "3", "volume": 30}]
        hash = tree.record_items("accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", items)
        new_items = [{"id": "1", "volume": 30}]
        updated_hash = tree.update_items(
            "accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", new_items, [], hash
        )
        recorded_items = tree.get_items_by_hash(updated_hash)
        assert recorded_items == {"1": new_items[0], "2": items[1], "3": items[2]}

        hashes = tree.get_hashes_by_hash(updated_hash)
        assert hashes == {
            "1": terminal_hash_manager.get_item_hash(new_items[0], "positions", "cloud-g1", "vint-hill"),
            "2": terminal_hash_manager.get_item_hash(items[1], "positions", "cloud-g1", "vint-hill"),
            "3": terminal_hash_manager.get_item_hash(items[2], "positions", "cloud-g1", "vint-hill"),
        }
        new_items_2 = [{"id": "3", "volume": 50}]
        updated_hash_2 = tree.update_items(
            "accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", new_items_2, [], updated_hash
        )
        recorded_items_2 = tree.get_items_by_hash(updated_hash_2)
        assert recorded_items_2 == {"1": new_items[0], "2": items[1], "3": new_items_2[0]}
        hashes_2 = tree.get_hashes_by_hash(updated_hash_2)
        assert hashes_2 == {
            "1": terminal_hash_manager.get_item_hash(new_items[0], "positions", "cloud-g1", "vint-hill"),
            "2": terminal_hash_manager.get_item_hash(items[1], "positions", "cloud-g1", "vint-hill"),
            "3": terminal_hash_manager.get_item_hash(new_items_2[0], "positions", "cloud-g1", "vint-hill"),
        }

    @pytest.mark.asyncio
    async def test_record_data_if_updated_without_parent_hash(self):
        """Should record data if updated without a parent hash."""
        items = [{'id': '1', 'volume': 10}, {'id': '2', 'volume': 20}]
        updated_hash = tree.update_items(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items, [], None
        )
        recorded_items = tree.get_items_by_hash(updated_hash)

        assert recorded_items == {'1': items[0], '2': items[1]}

    @pytest.mark.asyncio
    async def test_return_if_no_parent_data_found_during_update(self):
        """Should return if no parent data found during update."""
        items = [{'id': '1', 'volume': 10}, {'id': '2', 'volume': 20}]
        try:
            tree.update_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items, [], 'wrong')
            pytest.fail()
        except Exception as error:
            assert error.args[0] == "Parent data doesn't exist"

    @pytest.mark.asyncio
    async def test_remove_last_item_in_data(self):
        """Should remove last item in data."""
        items = [{"id": "1", "volume": 10}, {"id": "2", "volume": 20}, {"id": "3", "volume": 30}]
        hash = tree.record_items("accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", items)
        updated_hash = tree.update_items(
            "accountId", "cloud-g1", "connectionId", "vint-hill:1:ps-mpa-1", [], ["1", "2", "3"], hash
        )
        recorded_items = tree.get_items_by_hash(updated_hash)

        assert updated_hash is None
        assert recorded_items is None

    @pytest.mark.asyncio
    async def test_remove_items(self):
        """Should remove items."""
        items = [
            {'id': '1', 'volume': 10},
            {'id': '2', 'volume': 20},
            {'id': '3', 'volume': 30},
            {'id': '4', 'volume': 40},
        ]

        hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)

        await sleep(0.0005)

        updated_hash = tree.update_items(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], hash
        )
        recorded_items = tree.get_items_by_hash(updated_hash)

        assert recorded_items == {'1': items[0], '3': items[2], '4': items[3]}

        await sleep(0.0005)

        updated_hash_2 = tree.update_items(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2'], updated_hash
        )
        recorded_items_2 = tree.get_items_by_hash(updated_hash_2)

        assert updated_hash == updated_hash_2
        assert recorded_items_2 == {'1': items[0], '3': items[2], '4': items[3]}

        await sleep(0.0005)

        updated_hash_3 = tree.update_items(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3'], updated_hash_2
        )
        recorded_items_3 = tree.get_items_by_hash(updated_hash_3)

        assert recorded_items_3 == {'1': items[0], '4': items[3]}

        await sleep(0.0005)

        updated_hash_4 = tree.update_items(
            'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['3', '4'], updated_hash_3
        )
        recorded_items_4 = tree.get_items_by_hash(updated_hash_4)

        assert recorded_items_4 == {'1': items[0]}

    @pytest.mark.asyncio
    async def test_optimize_tree(self):
        """Should optimize tree."""
        with freeze_time() as frozen_datetime:
            items = [
                {'id': '1', 'volume': 10},
                {'id': '2', 'volume': 20},
                {'id': '3', 'volume': 30},
                {'id': '4', 'volume': 40},
            ]

            hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)
            await sleep(0.06)
            updated_hash = tree.update_items(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '4'], hash
            )
            await sleep(0.06)
            updated_hash_2 = tree.update_items(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '3'], updated_hash
            )
            recorded_items = tree.get_items_by_hash(updated_hash_2)

            assert recorded_items == {'1': items[0]}

            frozen_datetime.tick(550)
            await sleep(0.55)
            recorded_items_2 = tree.get_items_by_hash(updated_hash_2)

            assert recorded_items_2 == {'1': items[0]}

    @pytest.mark.asyncio
    async def test_remove_connection_references(self):
        """Should remove connection references."""
        with freeze_time() as frozen_datetime:
            items = [{'id': '1', 'volume': 10}]
            items_hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)
            frozen_datetime.tick(960)
            await sleep(0.96)
            items_data = tree.get_items_by_hash(items_hash)

            assert items_data == {'1': {'id': '1', 'volume': 10}}

            tree.remove_reference('connectionId', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(960)
            await sleep(0.96)
            items_data_2 = tree.get_items_by_hash(items_hash)

            assert items_data_2 is None

    @pytest.mark.asyncio
    async def test_get_last_used_hashes(self):
        """Should get last used hashes."""
        items = [
            {'id': '1', 'volume': 10},
            {'id': '2', 'volume': 20},
            {'id': '3', 'volume': 30},
            {'id': '4', 'volume': 40},
        ]
        hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)
        await sleep(0.0005)
        tree.record_items('accountId2', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [items[0]])
        await sleep(0.0005)
        hash_3 = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [items[1]])
        last_used_hashes = tree.get_last_used_hashes('accountId')

        assert last_used_hashes == [hash_3, hash]

    @pytest.mark.asyncio
    async def test_not_include_none_as_last_used_hash(self):
        """Should not include None as last used hash."""
        with freeze_time() as frozen_datetime:
            items = [{'id': '1', 'volume': 10}]
            hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)
            await sleep(0.0005)
            frozen_datetime.tick(0.5)
            tree.update_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['1'], hash)
            last_used_hashes = tree.get_last_used_hashes('accountId')

            assert last_used_hashes == [hash]

    @pytest.mark.asyncio
    async def test_get_fuzzy_last_used_hashes(self):
        """Should get fuzzy last used hashes."""
        data_1 = [
            {'symbol': 'EURUSD', 'tickSize': 0.0001},
            {'symbol': 'GBPUSD'},
            {'symbol': 'CADUSD', 'tickSize': 0.001},
        ]
        data_2 = [
            {'symbol': 'EURUSD', 'tickSize': 0.0002},
            {'symbol': 'GBPUSD'},
            {'symbol': 'CADUSD', 'tickSize': 0.002},
        ]
        data_3 = [
            {'symbol': 'EURUSD', 'tickSize': 0.0003},
            {'symbol': 'GBPUSD'},
            {'symbol': 'CADUSD', 'tickSize': 0.003},
        ]
        hash_1 = fuzzy_tree.record_items('ICMarkets-Demo01', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', data_1)
        hash_2 = fuzzy_tree.record_items('ICMarkets-Demo02', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', data_2)
        fuzzy_tree.record_items('Other-Server', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', data_3)
        last_used_hashes = fuzzy_tree.get_last_used_hashes('ICMarkets-Demo01')

        assert last_used_hashes == [hash_1, hash_2]

    @pytest.mark.asyncio
    async def test_add_reference(self):
        """Should add reference."""
        with freeze_time() as frozen_datetime:
            items = [
                {'id': '1', 'volume': 10},
                {'id': '2', 'volume': 20},
                {'id': '3', 'volume': 30},
                {'id': '4', 'volume': 40},
            ]
            expected = {'1': items[0], '2': items[1], '3': items[2], '4': items[3]}
            hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)

            try:
                tree.add_reference('wronghash', 'connectionId', 'vint-hill:1:ps-mpa-1')
                pytest.exit()
            except Exception as err:
                assert err.args[0] == "Can't add reference - positions data for hash wronghash doesn't exist"

            tree.add_reference(hash, 'connectionId2', 'vint-hill:1:ps-mpa-1')
            result = tree.get_items_by_hash(hash)

            assert result == expected

            frozen_datetime.tick(550)
            await sleep(0.55)
            result_2 = tree.get_items_by_hash(hash)

            assert result_2 == expected

            tree.remove_reference('connectionId', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(550)
            await sleep(0.55)
            result_3 = tree.get_items_by_hash(hash)

            assert result_3 == expected

            tree.remove_reference('connectionId2', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(550)
            await sleep(0.55)
            result_4 = tree.get_items_by_hash(hash)

            assert result_4 is None

    @pytest.mark.asyncio
    async def test_hand_over_children_to_parent_if_middle_optimized_out(self):
        """Should hand over children to the parent if the middle record is optimized out."""
        with freeze_time() as frozen_datetime:
            items = [
                {'id': '1', 'volume': 10},
                {'id': '2', 'volume': 20},
                {'id': '3', 'volume': 30},
                {'id': '4', 'volume': 40},
            ]
            hash = tree.record_items('accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', items)
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash = tree.update_items(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '4'], hash
            )
            frozen_datetime.tick(60)
            await sleep(0.06)
            updated_hash_2 = tree.update_items(
                'accountId', 'cloud-g1', 'connectionId', 'vint-hill:1:ps-mpa-1', [], ['2', '3'], updated_hash
            )
            tree.add_reference(hash, 'connectionId2', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(550)
            await sleep(0.55)
            tree.remove_reference('connectionId2', 'vint-hill:1:ps-mpa-1')
            frozen_datetime.tick(550)
            await sleep(0.55)
            new_hash = tree.update_items(
                'accountId',
                'cloud-g1',
                'connectionId',
                'vint-hill:1:ps-mpa-1',
                [{'id': '4', 'volume': 30}],
                [],
                updated_hash_2,
            )
            data = tree.get_items_by_hash(new_hash)

            assert data == {'1': {'id': '1', 'volume': 10}, '4': {'id': '4', 'volume': 30}}
