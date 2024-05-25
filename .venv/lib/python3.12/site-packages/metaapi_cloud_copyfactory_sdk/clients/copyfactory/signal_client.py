from copy import deepcopy
from typing import List

from .copyfactory_models import (
    CopyFactoryExternalSignalUpdate,
    CopyFactoryExternalSignalRemove,
    CopyFactoryTradingSignal,
    CopyFactoryExternalSignal,
)
from ..domain_client import DomainClient
from ...models import convert_iso_time_to_date, format_request, random_id


class SignalClient:
    """CopyFactory client for signal requests."""

    def __init__(self, account_id: str, host: dict, domain_client: DomainClient):
        """Initializes CopyFactory signal client instance.

        Args:
            account_id: Account id.
            host: Host data.
            domain_client: Domain client.
        """
        self._account_id = account_id
        self._domain_client = domain_client
        self._host = host

    @staticmethod
    def generate_signal_id():
        """Generates random signal id.

        Returns:
            Signal id.
        """
        return random_id(8)

    async def get_trading_signals(self) -> 'List[CopyFactoryTradingSignal]':
        """Returns trading signals the subscriber is subscribed to. See
        https://metaapi.cloud/docs/copyfactory/restApi/api/trading/getTradingSignals/

        Returns:
            A coroutine which resolves with signals found.
        """
        opts = {
            'url': f'/users/current/subscribers/{self._account_id}/signals',
            'method': 'GET',
            'headers': {'auth-token': self._domain_client.token},
        }
        result = await self._domain_client.request_signal(opts, self._host, self._account_id)
        convert_iso_time_to_date(result)
        return result

    async def get_strategy_external_signals(self, strategy_id: str) -> 'List[CopyFactoryExternalSignal]':
        """Returns active external signals of a strategy. Requires access to
        copyfactory-api:rest:public:external-signals:getSignals method which is included into reader role.
        Requires access to strategy, account resources.

        Args:
            strategy_id: Strategy id.

        Returns:
            A coroutine which resolves with external signals found.
        """
        opts = {
            'url': f'/users/current/strategies/{strategy_id}/external-signals',
            'method': 'GET',
            'headers': {'auth-token': self._domain_client.token},
        }
        result = await self._domain_client.request_signal(opts, self._host, self._account_id)
        convert_iso_time_to_date(result)
        return result

    async def update_external_signal(self, strategy_id: str, signal_id: str, signal: CopyFactoryExternalSignalUpdate):
        """Updates external signal for a strategy. See
        https://metaapi.cloud/docs/copyfactory/restApi/api/trading/updateExternalSignal/

        Args:
            strategy_id: Strategy id.
            signal_id: External signal id (should be 8 alphanumerical symbols)
            signal: Signal update payload.

        Returns:
            A coroutine which resolves when external signal is updated.
        """
        payload: dict = deepcopy(signal)
        format_request(payload)
        opts = {
            'url': f"/users/current/strategies/{strategy_id}/external-signals/{signal_id}",
            'method': 'PUT',
            'headers': {'auth-token': self._domain_client.token},
            'body': payload,
        }
        return await self._domain_client.request_signal(opts, self._host, self._account_id)

    async def remove_external_signal(self, strategy_id: str, signal_id: str, signal: CopyFactoryExternalSignalRemove):
        """Removes (closes) external signal for a strategy. See
        https://metaapi.cloud/docs/copyfactory/restApi/api/trading/removeExternalSignal/

        Args:
            strategy_id: Strategy id.
            signal_id: External signal id
            signal: Signal removal payload.

        Returns:
            A coroutine which resolves when external signal is removed.
        """
        payload: dict = deepcopy(signal)
        format_request(payload)
        opts = {
            'url': f"/users/current/strategies/{strategy_id}/external-signals/{signal_id}/remove",
            'method': 'POST',
            'headers': {'auth-token': self._domain_client.token},
            'body': payload,
        }
        return await self._domain_client.request_signal(opts, self._host, self._account_id)
