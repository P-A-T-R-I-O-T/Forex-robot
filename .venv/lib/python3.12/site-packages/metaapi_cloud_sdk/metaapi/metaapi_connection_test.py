import asyncio
from typing import List

import pytest
from mock.mock import MagicMock, AsyncMock

from lib.clients.metaapi.metaapi_websocket_client import MetaApiWebsocketClient
from lib.metaapi.metaapi_connection import MetaApiConnection
from lib.metaapi.metatrader_account import MetatraderAccount
from lib.metaapi.metatrader_account_replica import MetatraderAccountReplica


class MockMetaApiConnection(MetaApiConnection):
    async def connect(self, instance_id: str):
        pass

    async def close(self, instance_id: str):
        pass


class MockMetatraderAccountReplica(MetatraderAccountReplica):
    def __init__(self, id: str, region: str):
        super().__init__(MagicMock(), MagicMock(), MagicMock())
        self._id = id
        self._region = region

    @property
    def id(self) -> str:
        return self._id

    @property
    def region(self) -> str:
        return self._region


class MockAccount(MetatraderAccount):
    def __init__(self, id: str, region: str, replicas: List[MockMetatraderAccountReplica], account_regions: dict):
        super().__init__(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        self._id = id
        self._region = region
        self._replicas = replicas
        self._account_regions = account_regions

    @property
    def id(self) -> str:
        return self._id

    @property
    def region(self) -> str:
        return self._region

    @property
    def replicas(self) -> List[MockMetatraderAccountReplica]:
        return self._replicas

    @property
    def account_regions(self) -> dict:
        return self._account_regions


options = {'region': None, 'connections': {'refreshReplicasMaxDelayInMs': 0}}
websocket_client: MetaApiWebsocketClient = None
account: MetatraderAccount = None
connection: MockMetaApiConnection = None


@pytest.fixture(autouse=True)
async def run_around_tests():
    global websocket_client
    websocket_client = MagicMock()
    global account
    account = MockAccount(MagicMock(), MagicMock(), MagicMock(), MagicMock())
    global connection
    connection = MockMetaApiConnection(options, websocket_client, account)


class TestMetaApiConnectionScheduleRefresh:
    @pytest.fixture
    def prepare_account(self):
        replicas = [MockMetatraderAccountReplica('replica1', 'region2')]
        account_regions = {'region1': 'account1', 'region2': 'replica1'}
        account._id = 'account1'
        account._region = 'region'
        account._replicas = replicas
        account._account_regions = account_regions

        async def reload():
            replicas.append(MockMetatraderAccountReplica('replica2', 'region3'))
            account_regions['region3'] = 'replica2'

        account.reload = AsyncMock(side_effect=reload)

    # maybe there's better alternative for mocking dict attrs
    @pytest.fixture
    def update_options(self):
        """Fixture yields function that updates options and restore original options at the end of test."""
        global options
        original_options = options.copy()

        def setattr(key: str, value):
            options[key] = value

        yield setattr

        options = original_options

    @pytest.mark.asyncio
    async def test_subscribe_to_replicas_of_all_regions_if_region_is_not_filtered_out_explicitly(self, prepare_account):
        """Should subscribe to replicas of all regions if the region is not filtered out explicitly."""
        websocket_client.ensure_subscribe = MagicMock()

        connection.schedule_refresh('region')
        await asyncio.sleep(0.025)

        assert websocket_client.ensure_subscribe.call_count == 6
        websocket_client.ensure_subscribe.assert_any_call('account1', 0)
        websocket_client.ensure_subscribe.assert_any_call('account1', 1)
        websocket_client.ensure_subscribe.assert_any_call('replica1', 0)
        websocket_client.ensure_subscribe.assert_any_call('replica1', 1)
        websocket_client.ensure_subscribe.assert_any_call('replica2', 0)
        websocket_client.ensure_subscribe.assert_any_call('replica2', 1)

    @pytest.mark.asyncio
    async def test_subscribe_to_replica_of_only_explicitly_configured_region_when_replicas_change(
        self, prepare_account, update_options
    ):
        """Should subscribe to replica of only explicitly configured region when replicas change."""
        update_options('region', 'region2')
        websocket_client.ensure_subscribe = MagicMock()

        connection.schedule_refresh('region')
        await asyncio.sleep(0.025)

        assert websocket_client.ensure_subscribe.call_count == 2
        websocket_client.ensure_subscribe.assert_any_call('replica1', 0)
        websocket_client.ensure_subscribe.assert_any_call('replica1', 1)
