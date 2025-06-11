import pytest
from tinkoff_client import TinkoffClient
from config import TINKOFF_TOKEN

@pytest.fixture
def tinkoff_client():
    with TinkoffClient(token=TINKOFF_TOKEN) as client:
        yield client

def test_get_candles(tinkoff_client):
    candles = tinkoff_client.get_candles(...)
    assert len(candles) > 0