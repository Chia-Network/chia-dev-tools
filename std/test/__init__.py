import io
import datetime
import pytimeparse
from unittest import TestCase
from blspy import AugSchemeMPL, G1Element, PrivateKey

from clvm.serialize import sexp_from_stream

from lib.std.types.sized_bytes import bytes32
from lib.std.types.ints import uint64
from lib.std.util.keys import public_key_for_index, private_key_for_index
from lib.std.sim.node import Node
from lib.std.types.program import Program
from lib.std.util.condition_tools import ConditionOpcode, conditions_by_opcode
from lib.std.spends.p2_delegated_puzzle_or_hidden_puzzle import puzzle_for_pk, solution_for_delegated_puzzle, calculate_synthetic_secret_key # standard_transaction
from lib.std.spends.defaults import DEFAULT_HIDDEN_PUZZLE, DEFAULT_HIDDEN_PUZZLE_HASH
from lib.std.sim.default_constants import DEFAULT_CONSTANTS
from lib.std.types.spend_bundle import SpendBundle
from lib.std.types.coin_solution import CoinSolution
from lib.std.types.coin_signature import sign_coin_solutions
from lib.std.types.coin import Coin
from lib.std.spends.chialisp import sha256tree
from lib.std.types.program import Program

duration_div = 86400.0
block_time = (600.0 / 32.0) / duration_div
# Allowed subdivisions of 1 coin
coin_mul = 1000000000000

class SpendResult:
    def __init__(self,result):
        self.result = result
        self.outputs = result['additions']

class CoinWrapper(Coin):
    def __init__(self, parent : Coin, puzzle_hash : bytes32, amt : uint64, source : Program):
        super().__init__(parent,puzzle_hash,amt)
        self.source = source

    def puzzle(self) -> Program:
        return self.source

    def puzzle_hash(self) -> bytes32:
        return self.puzzle().get_tree_hash()

    def contract(self):
        return ContractWrapper(DEFAULT_CONSTANTS.GENESIS_CHALLENGE, self.source)

# We have two cases for coins:
# - Wallet coins which contribute to the "wallet balance" of the user.
#   They enable a user to "spend money" and "take actions on the network"
#   that have monetary value.
#
# - Contract coins which either lock value or embody information and
#   services.  These also contain a chia balance but are used for purposes
#   other than a fungible, liquid, spendable resource.  They should not show
#   up in a "wallet" in the same way.  We should use them by locking value
#   into wallet coins.  We should ensure that value contained in a contract
#   coin is never destroyed.
class ContractWrapper:
    def __init__(self,genesis_challenge,source):
        self.genesis_challenge = genesis_challenge
        self.source = source

    def puzzle(self):
        return self.source

    def puzzle_hash(self):
        return self.source.get_tree_hash()

    def custom_coin(self, parent : Coin, amt : uint64):
        return CoinWrapper(parent.name(), self.puzzle_hash(), amt, self.source)

class Wallet:
    def __init__(self,parent,name,pk,priv):
        self.parent = parent
        self.name = name
        self.pk_ = pk
        self.priv_ = priv
        self.usable_coins = {}
        self.puzzle = puzzle_for_pk(self.pk())
        self.puzzle_hash = self.puzzle.get_tree_hash()

    # Make this coin available to the user it goes with.
    def add_coin(self,coin):
        self.usable_coins[coin.name()] = coin

    # Find a coin containing amt we can use as a parent.
    def choose_coin(self,amt) -> CoinWrapper:
        for k,c in self.usable_coins.items():
            if c.amount >= amt:
                return CoinWrapper(c.parent_coin_info, c.puzzle_hash, c.amount, self.puzzle)

        return None

    # Create a new contract based on a parent coin.
    def launch_contract(self,source,**kwargs) -> CoinWrapper:
        amt = 1
        if 'amt' in kwargs:
            amt = kwargs['amt']

        amt = int(amt * coin_mul)

        found_coin = self.choose_coin(amt)
        if found_coin is None:
            raise ValueError(f'could not find available coin containing {amt} mojo')

        # Create a puzzle based on the incoming contract
        cw = ContractWrapper(DEFAULT_CONSTANTS.GENESIS_CHALLENGE, source)
        delegated_puzzle_solution = Program.to((1, [[ConditionOpcode.CREATE_COIN, cw.puzzle_hash(), amt]]))
        solution = Program.to([[], delegated_puzzle_solution, []])

        # Sign the (delegated_puzzle_hash + coin_name) with synthetic secret key
        signature = AugSchemeMPL.sign(
            calculate_synthetic_secret_key(self.priv_,DEFAULT_HIDDEN_PUZZLE_HASH),
            (delegated_puzzle_solution.get_tree_hash() + found_coin.name() + DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA)
        )

        spend_bundle = SpendBundle(
            [
                CoinSolution(
                    found_coin, # Coin to spend
                    self.puzzle, # Puzzle used for found_coin
                    solution, # The solution to the puzzle locking found_coin
                )
            ]
            , signature
        )
        pushed = self.parent.push_tx(spend_bundle)
        if pushed:
            return cw.custom_coin(found_coin, amt)
        else:
            return None

    def clear_coins(self):
        self.usable_coins = {}

    def pk(self):
        return self.pk_

    def balance(self):
        return 0

    def spend_coin(self, coin : CoinWrapper, **kwargs):
        amt = 1
        if 'amt' in kwargs:
            amt = kwargs['amt']

        amt = int(amt * coin_mul)

        def pk_to_sk(pk: G1Element) -> PrivateKey:
            assert pk == self.pk()
            return self.priv_

        if not 'args' in kwargs:
            # Automatic arguments from the user's intention.
            solution_list = [[ConditionOpcode.CREATE_COIN, self.puzzle_hash, amt]]
            if 'remain' in kwargs:
                remainer = kwargs['remain']
                remain_amt = coin.amount - amt
                if isinstance(remainer, ContractWrapper):
                    solution_list.append([ConditionOpcode.CREATE_COIN, remainer.puzzle_hash(), remain_amt])
                elif isinstance(remainer, Wallet):
                    solution_list.append([ConditionOpcode.CREATE_COIN, remainer.puzzle_hash, remain_amt])
                else:
                    raise ValueError("remainer is not a waller or a contract")

            delegated_solution = Program.to((1, solution_list))
            # Solution is the solution for the old coin.
            solution = Program.to([[], delegated_solution, []])
        else:
            solution = Program.to([[], Program.to(kwargs['args']), []])

        solution_for_coin = CoinSolution(
            coin,
            coin.puzzle(),
            solution,
        )

        spend_bundle = sign_coin_solutions(
            [solution_for_coin],
            pk_to_sk,
            DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA,
            DEFAULT_CONSTANTS.MAX_BLOCK_COST_CLVM
        )

        pushed = self.parent.push_tx(SpendBundle.from_chia_spend_bundle(spend_bundle))
        if pushed:
            return SpendResult(pushed)
        else:
            return None

# A user oriented (domain specific) view of the chia network.
class Network:
    def __init__(self):
        self.wallets = {}
        self.time = datetime.timedelta(0)
        self.node = Node()
        self.nobody = self.make_wallet('nobody')
        self.wallets[str(self.nobody.pk())] = self.nobody

    def farm_block(self,**kwargs):
        farmer = self.nobody
        if 'farmer' in kwargs:
            farmer = kwargs['farmer']

        farm_duration = datetime.timedelta(block_time)
        farmed = self.node.farm_block(farmer.pk())

        for k, w in self.wallets.items():
            w.clear_coins()

        for coin in self.node.coins:
            for kw, w in self.wallets.items():
                if coin.puzzle_hash == w.puzzle_hash:
                    w.add_coin(coin)

        self.time += farm_duration
        return farmed

    def alloc_key(self):
        key_idx = len(self.wallets)
        pk = public_key_for_index(key_idx)
        priv = private_key_for_index(key_idx)
        return pk, priv

    def make_wallet(self,name):
        pk, priv = self.alloc_key()
        w = Wallet(self, name, pk, priv)
        self.wallets[str(w.pk())] = w
        return w

    def skip_time(self,t,**kwargs):
        target_duration = pytimeparse.parse(t)
        target_time = self.time + datetime.timedelta(target_duration / duration_div)
        while target_time > self.time:
            self.farm_block(**kwargs)

        # Or possibly aggregate farm_block results.
        return None

    def push_tx(self,bundle):
        res = self.node.push_tx(bundle)
        results = self.farm_block()
        return {
            'cost': res['cost'],
            'additions': results['additions'],
            'removals': results['removals']
        }

class TestGroup(TestCase):
    def setUp(self):
        self.network = Network()

    def __init__(self,t):
        super().__init__(t)
