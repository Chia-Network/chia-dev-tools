import pytest

from chialisp.test import setup as test_setup

class TestSomething:
    @pytest.fixture(scope="function")
    async def setup(self):
        network, alice, bob = await test_setup()
        yield network, alice, bob

    @pytest.mark.asyncio
    async def test_something(self, setup):
        network, alice, bob = setup
        try:
            pass
        finally:
            await network.close()
