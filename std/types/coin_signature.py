import asyncio
from blspy import G1Element
import chia.wallet.sign_coin_solutions as scs
from lib.std.types.spend_bundle import SpendBundle

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
    r = await scs.sign_coin_solutions(
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
    return SpendBundle.from_chia_spend_bundle(bf.contents)
