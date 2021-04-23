from typing import List

from lib.std.types.coin import Coin
from lib.std.types.program import Program
from lib.std.types.sized_bytes import bytes32
from lib.std.util.condition_tools import (
    conditions_dict_for_solution,
    created_outputs_for_conditions_dict,
)


def additions_for_solution(coin_name: bytes32, puzzle_reveal: Program, solution: Program, max_cost: int) -> List[Coin]:
    """
    Checks the conditions created by CoinSolution and returns the list of all coins created
    """
    err, dic, cost = conditions_dict_for_solution(puzzle_reveal, solution, max_cost)
    if err or dic is None:
        return []
    return created_outputs_for_conditions_dict(dic, coin_name)
