from pathlib import Path
from typing import List

from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.blockchain_format.program import Program
from chia.types.condition_opcodes import ConditionOpcode
from chia.util.ints import uint64
from chia.util.hash import std_hash

from clvm.casts import int_to_bytes

import cdv.clibs as std_lib
from cdv.util.load_clvm import load_clvm

clibs_path: Path = Path(std_lib.__file__).parent
PIGGYBANK_MOD: Program = load_clvm("piggybank.clsp", "cdv.examples.clsp", search_paths=[clibs_path])


# Create a piggybank
def create_piggybank_puzzle(amount: uint64, cash_out_puzhash: bytes32) -> Program:
    return PIGGYBANK_MOD.curry(amount, cash_out_puzhash)


# Generate a solution to contribute to a piggybank
def solution_for_piggybank(pb_coin: Coin, contrib_amount: uint64) -> Program:
    return Program.to([pb_coin.puzzle_hash, pb_coin.amount, (pb_coin.amount + contrib_amount)])


# Return the condition to assert the announcement
def piggybank_announcement_assertion(pb_coin: Coin, contrib_amount: uint64) -> List:
    return [
        ConditionOpcode.ASSERT_COIN_ANNOUNCEMENT,
        std_hash(pb_coin.name() + int_to_bytes(pb_coin.amount + contrib_amount)),
    ]
