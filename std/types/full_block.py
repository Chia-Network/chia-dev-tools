from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from lib.std.sim.mempool_check_conditions import get_name_puzzle_conditions
from lib.std.types.announcement import Announcement
from lib.std.types.coin import Coin
from lib.std.types.program import SerializedProgram
from lib.std.types.sized_bytes import bytes32
from lib.std.types.name_puzzle_condition import NPC
from lib.std.util.condition_tools import created_announcements_for_conditions_dict, created_outputs_for_conditions_dict
from lib.std.types.ints import uint32
from lib.std.types.streamable import Streamable, streamable


@dataclass(frozen=True)
@streamable
class FullBlock(Streamable):
    reward_claims_incorporated: List[Coin]
    transactions_generator: Optional[SerializedProgram] # Program that generates transactions
    height: uint32

    def get_included_reward_coins(self) -> Set[Coin]:
        return set(self.reward_claims_incorporated)

    def additions(self) -> List[Coin]:
        additions: List[Coin] = []

        if self.transactions_generator is not None:
            # This should never throw here, block must be valid if it comes to here
            err, npc_list, cost = get_name_puzzle_conditions(self.transactions_generator, False)
            # created coins
            if npc_list is not None:
                additions.extend(additions_for_npc(npc_list))

        additions.extend(self.get_included_reward_coins())

        return additions

    def tx_removals_and_additions(self) -> Tuple[List[bytes32], List[Coin]]:
        """
        Doesn't return farmer and pool reward.
        This call assumes that this block has been validated already,
        get_name_puzzle_conditions should not return error here
        """
        removals: List[bytes32] = []
        additions: List[Coin] = []

        if self.transactions_generator is not None:
            # This should never throw here, block must be valid if it comes to here
            err, npc_list, cost = get_name_puzzle_conditions(self.transactions_generator, False)
            # build removals list
            if npc_list is None:
                return [], []
            for npc in npc_list:
                removals.append(npc.coin_name)

            additions.extend(additions_for_npc(npc_list))

        return removals, additions


def additions_for_npc(npc_list: List[NPC]) -> List[Coin]:
    additions: List[Coin] = []

    for npc in npc_list:
        for coin in created_outputs_for_conditions_dict(npc.condition_dict, npc.coin_name):
            additions.append(coin)

    return additions


def announcements_for_npc(npc_list: List[NPC]) -> List[Announcement]:
    announcements: List[Announcement] = []

    for npc in npc_list:
        announcements.extend(created_announcements_for_conditions_dict(npc.condition_dict, npc.coin_name))

    return announcements
