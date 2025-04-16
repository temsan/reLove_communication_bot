import pytest

@pytest.mark.asyncio
async def test_example():
    """An example asynchronous test."""
    assert True

def test_sync_example():
    """An example synchronous test."""
    x = 1
    y = 1
    assert x == y 