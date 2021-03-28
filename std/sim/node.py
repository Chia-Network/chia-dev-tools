import time
from typing import List, Dict

from blspy import G1Element

from lib.std.types.coin import Coin
from lib.std.types.ints import uint32, uint64
from lib.std.types.sized_bytes import bytes32
from lib.std.types.spend_bundle import SpendBundle
from lib.std.types.mempool_inclusion_status import MempoolInclusionStatus
from lib.std.sim.coinbase import create_pool_coin, create_farmer_coin, create_puzzlehash_for_pk
from lib.std.sim.block_rewards import calculate_pool_reward, calculate_base_farmer_reward
from lib.std.sim.spend_bundle_validation import validate_spendbundle

class Node():
    block_height: uint32 = 0
    timestamp: uint64 = 0
    coins: List[Coin] = []
    mempool: List[SpendBundle] = []

    def __init__(self):
        self.timestamp = time.time()

    def set_block_height(self, block_height: uint32):
        self.block_height = height

    def set_timestamp(self, timestamp: uint64):
        self.timestamp = timestamp

    def add_coin(self, coin: Coin):
        self.coins.append(coin)

    def get_coins(self, coin_filter={}):
        filtered_coins = self.coins
        for key in coin_filter:
            filtered_coins = list(filter(lambda e: e[key] == coin_filter[key], filtered_coins))
        return filtered_coins

    def farm_block(self, public_key: G1Element):
        # Fees get calculated
        fees = 0
        for bundle in self.mempool:
            fees += bundle.fees()

        # Coins get moved
        removals = []
        additions = []
        for bundle in self.mempool:
            for removal in bundle.removals():
                removals.append(removal)
            for addition in bundle.additions():
                additions.append(addition)

        for removal in removals:
            self.coins.remove(removal)
        for addition in additions:
            self.coins.append(addition)

        # Rewards get generated
        self.coins.append(create_pool_coin(
            self.block_height,
            create_puzzlehash_for_pk(public_key),
            calculate_pool_reward(self.block_height)
        ))
        self.coins.append(create_farmer_coin(
            self.block_height,
            create_puzzlehash_for_pk(public_key),
            (calculate_base_farmer_reward(self.block_height) + fees)
        ))

        # mempool is cleared
        self.mempool = []

        # block_height is incremented
        self.block_height += 1

    def push_tx(self, spend_bundle: SpendBundle):
        spend_name = spend_bundle.name()

        removals = []
        for bundle in self.mempool:
            for removal in bundle.removals():
                removals.append(removal)

        if spend_bundle in self.mempool:
            status = MempoolInclusionStatus.SUCCESS
            error = None
        else:
            cost, status, error = validate_spendbundle(spend_bundle, removals, self.block_height)
            if status != MempoolInclusionStatus.SUCCESS:
                if spend_bundle in self.mempool:
                    # Already in mempool
                    status = MempoolInclusionStatus.SUCCESS
                    error = None

        if status == MempoolInclusionStatus.FAILED:
            assert error is not None
            raise ValueError(f"Failed to include transaction {spend_name}, error {error.name}")
        return {
            "status": status.name,
        }
