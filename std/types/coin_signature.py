import blspy
from blspy import AugSchemeMPL, G1Element, PrivateKey
from typing import Callable, List, Optional
import asyncio

from lib.std.types.spend_bundle import SpendBundle

from lib.std.types.coin_solution import CoinSolution
from lib.std.types.spend_bundle import SpendBundle
from lib.std.util.condition_tools import conditions_dict_for_solution, pkm_pairs_for_conditions_dict

async def chia_sign_coin_solutions(
    coin_solutions: List[CoinSolution],
    secret_key_for_public_key_f: Callable[[blspy.G1Element], Optional[PrivateKey]],
    additional_data: bytes,
    max_cost: int,
) -> SpendBundle:
    signatures: List[blspy.G2Element] = []
    pk_list: List[blspy.G1Element] = []
    msg_list: List[bytes] = []
    for coin_solution in coin_solutions:
        # Get AGG_SIG conditions
        err, conditions_dict, cost = conditions_dict_for_solution(
            coin_solution.puzzle_reveal, coin_solution.solution, max_cost
        )
        if err or conditions_dict is None:
            error_msg = f"Sign transaction failed, con:{conditions_dict}, error: {err}"
            raise ValueError(error_msg)

        # Create signature
        for pk, msg in pkm_pairs_for_conditions_dict(
            conditions_dict, bytes(coin_solution.coin.name()), additional_data
        ):
            pk_list.append(pk)
            msg_list.append(msg)
            secret_key = secret_key_for_public_key_f(pk)
            if secret_key is None:
                e_msg = f"no secret key for {pk}"
                raise ValueError(e_msg)
            assert bytes(secret_key.get_g1()) == bytes(pk)
            signature = AugSchemeMPL.sign(secret_key, msg)
            assert AugSchemeMPL.verify(pk, msg, signature)
            signatures.append(signature)

    # Aggregate signatures
    aggsig = AugSchemeMPL.aggregate(signatures)
    assert AugSchemeMPL.aggregate_verify(pk_list, msg_list, aggsig)
    return SpendBundle(coin_solutions, aggsig)

class BasicFuture:
    def __init__(self):
        self.contents = None

    def take_result(self,r):
        self.contents = r

async def call_sign_coin_solutions(
        future : BasicFuture,
        coin_solutions,
        secret_key_for_public_key_f,
        additional_data: bytes,
        max_cost: int,
) -> SpendBundle:
    r = await chia_sign_coin_solutions(
        coin_solutions,
        secret_key_for_public_key_f,
        additional_data,
        max_cost
    )
    future.take_result(r)

# Invokes chia's sign_coin_solutions and return a local style spend bundle.
# This is here because it does the right thing for nonstandard coin invocations.
def sign_coin_solutions(
        coin_solutions,
        secret_key_for_public_key_f,
        additional_data: bytes,
        max_cost: int,
) -> SpendBundle:
    bf = BasicFuture()
    asyncio.run(call_sign_coin_solutions(bf, coin_solutions, secret_key_for_public_key_f, additional_data, max_cost))
    return bf.contents
