import pytest

from cdv.test import Network

class TestCoins:

    @pytest.fixture(scope="function")
    async def setup(self):
        coin_multiple = 1000000000000
        network = await Network.create()
        await network.farm_block() # gives 21000000 chia!
        yield (coin_multiple, network)


    async def do_multi_spend(self, network, use_amount):
        alice = network.make_wallet('alice')
        bob = network.make_wallet('bob')

        # Farm for alice
        await network.farm_block(farmer=alice)
        await network.farm_block(farmer=alice)

        alice_start_balance = alice.balance()
        bob_start_balance = bob.balance()

        # Give 'amount' chia (for which we won't have a single coin big enough)
        # to bob.  This will only work if we're combining coins.
        result = await alice.give_chia(bob, use_amount)

        assert result

        assert bob.balance() == bob_start_balance + use_amount
        assert alice.balance() == alice_start_balance - use_amount

    @pytest.mark.asyncio
    async def test_1_chia(self, setup):
        try:
            coin_multiple, network = setup
            await self.do_multi_spend(network, 1 * coin_multiple)
        finally:
            await network.close()

    @pytest.mark.asyncio
    async def test_2_chia(self, setup):
        try:
            coin_multiple, network = setup
            await self.do_multi_spend(network, 2 * coin_multiple)
        finally:
            await network.close()

    @pytest.mark.asyncio
    async def test_3_chia(self, setup):
        try:
            coin_multiple, network = setup
            await self.do_multi_spend(network, 3 * coin_multiple)
        finally:
            await network.close()

    @pytest.mark.asyncio
    async def test_4_chia(self, setup):
        try:
            coin_multiple, network = setup
            await self.do_multi_spend(network, 4 * coin_multiple)
        finally:
            await network.close()
