from __future__ import annotations

from typing import Dict, List, Optional

import pytest
import pytest_asyncio
from chia.types.blockchain_format.coin import Coin
from chia.types.condition_opcodes import ConditionOpcode
from chia.types.spend_bundle import SpendBundle
from chia.util.ints import uint64

from cdv.examples.drivers.piggybank_drivers import (
    create_piggybank_puzzle,
    piggybank_announcement_assertion,
    solution_for_piggybank,
)
from cdv.test import CoinWrapper
from cdv.test import setup as setup_test


class TestStandardTransaction:
    @pytest_asyncio.fixture(scope="function")
    async def setup(self):
        async with setup_test() as (network, alice, bob):
            await network.farm_block()
            yield network, alice, bob

    async def make_and_spend_piggybank(self, network, alice, bob, CONTRIBUTION_AMOUNT) -> Dict[str, List[Coin]]:
        # Get our alice wallet some money
        await network.farm_block(farmer=alice)

        # This will use one mojo to create our piggybank on the blockchain.
        piggybank_coin: Optional[CoinWrapper] = await alice.launch_smart_coin(
            create_piggybank_puzzle(uint64(1000000000000), bob.puzzle_hash)
        )
        # This retrieves us a coin that is at least 500 mojos.
        contribution_coin: Optional[CoinWrapper] = await alice.choose_coin(CONTRIBUTION_AMOUNT)

        # Make sure everything succeeded
        if not piggybank_coin or not contribution_coin:
            raise ValueError("Something went wrong launching/choosing a coin")

        # This is the spend of the piggy bank coin.  We use the driver code to create the solution.
        piggybank_spend: SpendBundle = await alice.spend_coin(
            piggybank_coin,
            pushtx=False,
            args=solution_for_piggybank(piggybank_coin.coin, CONTRIBUTION_AMOUNT),
        )
        # This is the spend of a standard coin.  We simply spend to ourselves but minus the CONTRIBUTION_AMOUNT.
        contribution_spend: SpendBundle = await alice.spend_coin(
            contribution_coin,
            pushtx=False,
            amt=(contribution_coin.amount - CONTRIBUTION_AMOUNT),
            custom_conditions=[
                [
                    ConditionOpcode.CREATE_COIN,
                    contribution_coin.puzzle_hash,
                    (contribution_coin.amount - CONTRIBUTION_AMOUNT),
                ],
                piggybank_announcement_assertion(piggybank_coin.coin, CONTRIBUTION_AMOUNT),
            ],
        )

        # Aggregate them to make sure they are spent together
        combined_spend = SpendBundle.aggregate([contribution_spend, piggybank_spend])

        result: Dict[str, List[Coin]] = await network.push_tx(combined_spend)
        return result

    @pytest.mark.asyncio
    async def test_piggybank_contribution(self, setup):
        network, alice, bob = setup
        try:
            result: Dict[str, List[Coin]] = await self.make_and_spend_piggybank(network, alice, bob, 500)

            assert "error" not in result

            # Make sure there is exactly one piggybank with the new amount
            filtered_result: List[Coin] = list(
                filter(
                    lambda addition: (addition.amount == 501)
                    and (
                        addition.puzzle_hash == create_piggybank_puzzle(1000000000000, bob.puzzle_hash).get_tree_hash()
                    ),
                    result["additions"],
                )
            )
            assert len(filtered_result) == 1
        finally:
            pass

    @pytest.mark.asyncio
    async def test_piggybank_completion(self, setup):
        network, alice, bob = setup
        try:
            result: Dict[str, List[Coin]] = await self.make_and_spend_piggybank(network, alice, bob, 1000000000000)

            assert "error" not in result

            # Make sure there is exactly one piggybank with value 0
            filtered_result: List[Coin] = list(
                filter(
                    lambda addition: (addition.amount == 0)
                    and (
                        addition.puzzle_hash == create_piggybank_puzzle(1000000000000, bob.puzzle_hash).get_tree_hash()
                    ),
                    result["additions"],
                )
            )
            assert len(filtered_result) == 1

            # Make sure there is exactly one coin that has been cashed out to bob
            filtered_result: List[Coin] = list(
                filter(
                    lambda addition: (addition.amount == 1000000000001) and (addition.puzzle_hash == bob.puzzle_hash),
                    result["additions"],
                )
            )
            assert len(filtered_result) == 1
        finally:
            pass

    @pytest.mark.asyncio
    async def test_piggybank_stealing(self, setup):
        network, alice, bob = setup
        try:
            result: Dict[str, List[Coin]] = await self.make_and_spend_piggybank(network, alice, bob, -100)
            assert "error" in result
            assert (
                "GENERATOR_RUNTIME_ERROR" in result["error"]
            )  # This fails during puzzle execution, not in driver code
        finally:
            pass
