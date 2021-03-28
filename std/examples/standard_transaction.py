from blspy import AugSchemeMPL

from lib.std.sim.node import Node
from lib.std.util.keys import public_key_for_index, private_key_for_index
from lib.std.types.spend_bundle import SpendBundle
from lib.std.types.coin_solution import CoinSolution
from lib.std.types.condition_opcodes import ConditionOpcode
from lib.std.types.program import Program
from lib.std.types.sized_bytes import bytes32
from lib.std.spends.p2_delegated_puzzle_or_hidden_puzzle import puzzle_for_pk, solution_for_delegated_puzzle, calculate_synthetic_secret_key
from lib.std.spends.defaults import DEFAULT_HIDDEN_PUZZLE_HASH

node = Node()
public_key = public_key_for_index(0)
private_key = private_key_for_index(0)

#Farm a couple of blocks to populate some coins
node.farm_block(public_key)
node.farm_block(public_key)

#Create a puzzle that just outputs a new coin locked up with standard puzzle hash
delegated_puzzle = Program.to((1, [[ConditionOpcode.CREATE_COIN, puzzle_for_pk(public_key).get_tree_hash(), 250000000000]]))

#Sign the (delegated_puzzle_hash + coin_name) with synthetic secret key
signature = AugSchemeMPL.sign(
    calculate_synthetic_secret_key(private_key,DEFAULT_HIDDEN_PUZZLE_HASH),
    (delegated_puzzle.get_tree_hash() + node.coins[3].name())
)

#Create a spend bundle with the above information
bundle = SpendBundle(
    [
        CoinSolution(
            node.coins[3], #coin being spent
            puzzle_for_pk(public_key), #puzzle reveal
            Program.to([[], delegated_puzzle, []]) #puzzle solution
        )
    ],
    signature
)

#Attempt to spend the bundle
print(node.push_tx(bundle))
