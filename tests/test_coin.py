import pytest

from chialisp.test import Network
from chia.types.blockchain_format.program import Program
from chia.wallet.puzzles.load_clvm import load_clvm

class TestCoins:
    # Imagine we have coin that lets bob spend it after 60 seconds, or alice at any time.
    @pytest.fixture(scope="function")
    async def start_test(self):
        try:
            coin_multiple = 1000000000000
            network = await Network.create()
            coin_amount = int(0.0987654321 * coin_multiple)

            template_program = load_clvm('template.clvm', 'tests')

            # Make wallets for our actors.
            alice = network.make_wallet('alice')
            bob = network.make_wallet('bob')

            # Load the contract and set alice and bob as the participants.
            coin_source = template_program.curry(
                alice.puzzle_hash,
                bob.puzzle_hash,
                coin_amount,
                60
            )

            # Time skipping allows us to farm some coins.
            await network.skip_time("10s", farmer=alice)
            await network.skip_time("10s", farmer=bob)

            # Check that the bundle can be launched
            time_coin = await alice.launch_contract(coin_source, amt=coin_amount)
            assert time_coin

            # Return the contract's new coin and the actors.
            return network, time_coin, coin_amount, alice, bob
        except:
            await network.close()

    # Check that bob can't spend the coin right away.
    @pytest.mark.asyncio
    async def test_bob_cant_spend(self, start_test):
        try:
            network, time_coin, coin_amount, alice, bob = start_test
            bob_start_balance = bob.balance()

            res = await bob.spend_coin(time_coin)

            assert res.error
            assert bob.balance() <= bob_start_balance
        finally:
            await network.close()

    # Check that alice cna spend the coin right away.
    @pytest.mark.asyncio
    async def test_alice_can_recover(self, start_test):
        try:
            network, time_coin, coin_amount, alice, bob = start_test
            alice_start_balance = alice.balance()

            # Check that alice can spend before 60 seconds..
            res = await alice.spend_coin(time_coin, args=[alice.puzzle_hash])

            assert alice.balance() == alice_start_balance + coin_amount
        finally:
            await network.close()

    # Check that bob can spend the coin after the timeout.
    @pytest.mark.asyncio
    async def test_bob_can_spend_later(self, start_test):
        try:
            network, time_coin, coin_amount, alice, bob = start_test
            bob_start_balance = bob.balance()

            # Check that bob can spend after interval
            await network.skip_time('5m')
            res = await bob.spend_coin(time_coin, args=[bob.puzzle_hash])
            bob_payment = res.find_standard_coins(bob.puzzle_hash)
            assert bob.balance() == bob_start_balance + coin_amount
        finally:
            await network.close()