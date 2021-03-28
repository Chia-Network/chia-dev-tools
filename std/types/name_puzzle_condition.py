from dataclasses import dataclass
from typing import Dict, List, Tuple

from lib.std.types.sized_bytes import bytes32
from lib.std.types.condition_var_pair import ConditionVarPair
from lib.std.types.streamable import Streamable, streamable
from lib.std.util.condition_tools import ConditionOpcode, created_outputs_for_conditions_dict, created_announcements_for_conditions_dict
from lib.std.types.coin import Coin
from lib.std.types.announcement import Announcement


@dataclass(frozen=True)
@streamable
class NPC(Streamable):
    coin_name: bytes32
    puzzle_hash: bytes32
    conditions: List[Tuple[ConditionOpcode, List[ConditionVarPair]]]

    @property
    def condition_dict(self):
        d: Dict[ConditionOpcode, List[ConditionVarPair]] = {}
        for opcode, l in self.conditions:
            d[opcode] = l
        return d

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
