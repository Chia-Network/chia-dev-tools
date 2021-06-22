import io
import datetime
import pytimeparse
from unittest import TestCase
from blspy import AugSchemeMPL, G1Element, PrivateKey

from clvm.serialize import sexp_from_stream
from clvm import SExp

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
from lib.std.util.hash import std_hash

CONDITION_CREATE_COIN = 51
CONDITION_CREATE_COIN_ANNOUNCEMENT = 60
CONDITION_ASSERT_COIN_ANNOUNCEMENT = 61

duration_div = 86400.0
block_time = (600.0 / 32.0) / duration_div
# Allowed subdivisions of 1 coin

class SpendResult:
    def __init__(self,result):
        """Constructor for internal use.

        error - a string describing the error or None
        result - the raw result from Network::push_tx
        outputs - a list of new Coin objects surviving the transaction
        """
        self.result = result
        if 'error' in result:
            self.error = result['error']
            self.outputs = []
        else:
            self.error = None
            self.outputs = result['additions']

    def find_standard_coins(self,puzzle_hash):
        """Given a Wallet's puzzle_hash, find standard coins usable by it.

        These coins are recognized as changing the Wallet's chia balance and are
        usable for any purpose."""
        return list(filter(lambda x: x.puzzle_hash == puzzle_hash, self.outputs))

class CoinWrapper(Coin):
    """A class that provides some useful methods on coins."""
    def __init__(self, parent : Coin, puzzle_hash : bytes32, amt : uint64, source : Program):
        """Given parent, puzzle_hash and amount, give an object representing the coin"""
        super().__init__(parent,puzzle_hash,amt)
        self.source = source

    def puzzle(self) -> Program:
        """Return the program that unlocks this coin"""
        return self.source

    def puzzle_hash(self) -> bytes32:
        """Return this coin's puzzle hash"""
        return self.puzzle().get_tree_hash()

    def contract(self):
        """Return a contract object wrapping this coin's program"""
        return ContractWrapper(DEFAULT_CONSTANTS.GENESIS_CHALLENGE, self.source)

    def create_standard_spend(self, priv, conditions):
        delegated_puzzle_solution = Program.to((1, conditions))
        solution = Program.to([[], delegated_puzzle_solution, []])

        coin_solution_object = CoinSolution(
            self,
            self.puzzle(),
            solution,
        )

        # Create a signature for each of these.  We'll aggregate them at the end.
        signature = AugSchemeMPL.sign(
            calculate_synthetic_secret_key(priv, DEFAULT_HIDDEN_PUZZLE_HASH),
            (delegated_puzzle_solution.get_tree_hash() + self.name() + DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA)
        )

        return coin_solution_object, signature

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
        """A wrapper for a contract carrying useful methods for interacting with chia."""
        self.genesis_challenge = genesis_challenge
        self.source = source

    def puzzle(self):
        """Give this contract's program"""
        return self.source

    def puzzle_hash(self):
        """Give this contract's puzzle hash"""
        return self.source.get_tree_hash()

    def custom_coin(self, parent : Coin, amt : uint64):
        """Given a parent and an amount, create the Coin object representing this
        contract as it would exist post launch"""
        return CoinWrapper(parent.name(), self.puzzle_hash(), amt, self.source)

class CoinPairSearch:
    def __init__(self,target_amount):
        self.target = target_amount
        self.best_fit = []
        self.max_coins = []

    def get_result(self):
        return self.best_fit, self.max_coins

    def process_coin_for_combine_search(self,coin):
        # Update max
        if len(self.max_coins) < 2:
            self.max_coins = self.max_coins + [coin]
        elif coin.amount > self.max_coins[0].amount:
            self.max_coins = ([coin] + self.max_coins)[:2]
        elif coin.amount > self.max_coins[1].amount:
            self.max_coins = [self.max_coins[0], coin]

        # Update best
        if len(self.best_fit) < 2:
            self.best_fit = self.best_fit + [coin]
        else:
            cur_best_fit_amount = sum(map(lambda x: x.amount, self.best_fit))
            greater = 0 if self.best_fit[0].amount > self.best_fit[1].amount else 1
            lesser = (greater + 1) % 2
            candidate_bf_amount = self.best_fit[lesser].amount + coin.amount
            if candidate_bf_amount < cur_best_fit_amount and candidate_bf_amount > self.target:
                self.best_fit = [self.best_fit[lesser], coin]

# A basic wallet that knows about standard coins.
# We can use this to track our balance as an end user and keep track of chia
# that is released by contracts, if the contracts interact meaningfully with
# them, as many likely will.
class Wallet:
    def __init__(self,parent,name,pk,priv):
        """Internal use constructor, use Network::make_wallet

        Fields:
        parent - The Network object that created this Wallet
        name - The textural name of the actor
        pk_ - The actor's public key
        priv_ - The actor's private key
        usable_coins - Standard coins spendable by this actor
        puzzle - A program for creating this actor's standard coin
        puzzle_hash - The puzzle hash for this actor's standard coin
        """
        self.parent = parent
        self.name = name
        self.pk_ = pk
        self.priv_ = priv
        self.usable_coins = {}
        self.puzzle = puzzle_for_pk(self.pk())
        self.puzzle_hash = self.puzzle.get_tree_hash()

    def __repr__(self):
        return f'<Wallet(name={self.name},puzzle_hash={self.puzzle_hash},pk={self.pk_})>'

    # Make this coin available to the user it goes with.
    def add_coin(self,coin):
        self.usable_coins[coin.name()] = coin

    def compute_combine_action(self,amt,actions,usable_coins):
        # No point in going on if we're on our last dollar.
        if len(usable_coins) < 2:
            return None

        # No one coin is enough, try to find a best fit pair, otherwise combine the two
        # maximum coins.
        searcher = CoinPairSearch(amt)

        # Process coins for this round.
        for k,c in usable_coins.items():
            searcher.process_coin_for_combine_search(c)

        best_fit, max_coins = searcher.get_result()

        # Best fit coins indicate we can combine just 2, so do that.
        if len(best_fit) == 2:
            return actions + [best_fit]
        else:
            del usable_coins[max_coins[0].name()]
            del usable_coins[max_coins[1].name()]
            new_coin = CoinWrapper(
                max_coins[0],
                self.puzzle_hash,
                max_coins[0].amount + max_coins[1].amount,
                self.puzzle
            )
            usable_coins[new_coin.name()] = new_coin
            return compute_combine_action(amt, actions + [max_coins], usable_coins)

    # Given some coins, combine them, causing the network to make us
    # recompute our balance in return.
    #
    # This is a metaphor for the meaning of "solution" in the coin "puzzle program" context:
    #
    #     The arguments to the coin's puzzle program, which is the first kind
    #     of object called a 'solution' in this case refers to the arguments
    #     needed to cause the program to emit blockchain compatible opcodes.
    #     It's a "puzzle" in the sense that a ctf RE exercise is a "puzzle".
    #     "solving" it means producing input that causes the unknown program to
    #     do something desirable.
    #
    # Spending multiple coins:
    #   There are two running lists that need to be kept when spending multiple coins:
    #
    #   - A list of signatures.  Each coin has its own signature requirements, but standard
    #     coins are signed like this:
    #
    #             AugSchemeMPL.sign(
    #               calculate_synthetic_secret_key(self.priv_,DEFAULT_HIDDEN_PUZZLE_HASH),
    #               (delegated_puzzle_solution.get_tree_hash() + c.name() + DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA)
    #             )
    #
    #     where c.name is the coin's "name" (in the code) or coinID (in the
    #     chialisp docs). delegated_puzzle_solution is a clvm program that
    #     produces the arguments we want to give the puzzle program (the first
    #     kind of 'solution').
    #
    #     In most cases, we'll give a tuple like (1, [some, python, [data,
    #     here]]) for these arguments, because '1' is the quote function 'q' in
    #     clvm. One could write this program with any valid clvm code though.
    #     The important thing is that it's runnable code, not literal data as
    #     one might expect.
    #
    #   - A list of CoinSolution objects.
    #     Theese consist of (with c : Coin):
    #
    #             CoinSolution(
    #               c,
    #               c.puzzle(),
    #               solution,
    #             )
    #
    # Where solution is a second formulation of a 'solution' to a puzzle (the third form
    # of 'solution' we'll use in this documentation is the CoinSolution object.).  This is
    # related to the program arguments above, but prefixes and suffixes an empty list on
    # them (admittedly i'm cargo culting this part):
    #
    # solution = Program.to([[], delegated_puzzle_solution, []])
    #
    # So you do whatever you want with a bunch of coins at once and now you have two lists:
    # 1) A list of G1Element objects yielded by AugSchemeMPL.sign
    # 2) A list of CoinSolution objects.
    #
    # Now to spend them at once:
    #
    #         signature = AugSchemeMPL.aggregate(signatures)
    #         spend_bundle = SpendBundle(coin_solutions, signature)
    #
    def combine_coins(self,coins):
        # Overall structure:
        # Create len-1 spends that just assert that the final coin is created with full value.
        # Create 1 spend for the final coin that asserts the other spends occurred and
        # Creates the new coin.

        beginning_balance = self.balance()
        beginning_coins = len(self.usable_coins)

        def pk_to_sk(pk: G1Element) -> PrivateKey:
            assert pk == self.pk()
            return self.priv_

        # We need the final coin to know what the announced coin name will be.
        final_coin = CoinWrapper(
            coins[-1].name(),
            self.puzzle_hash,
            sum(map(lambda x: x.amount, coins)),
            self.puzzle
        )

        destroyed_coin_solutions = []

        # Each coin wants agg_sig_me so we aggregate them at the end.
        signatures = []

        for c in coins[:-1]:
            announce_conditions = [
                # each coin announces its name to alert the final coin that it spent
                [
                    CONDITION_CREATE_COIN_ANNOUNCEMENT,
                    c.name()
                ],
                # Each coin expects the final coin creation announcement
                [
                    CONDITION_ASSERT_COIN_ANNOUNCEMENT,
                    std_hash(coins[-1].name() + final_coin.name())
                ]
            ]

            coin_solution, signature = c.create_standard_spend(self.priv_, announce_conditions)
            destroyed_coin_solutions.append(coin_solution)
            signatures.append(signature)

        final_coin_creation = list(map(lambda x: [
            CONDITION_ASSERT_COIN_ANNOUNCEMENT,
            std_hash(c.name() + c.name()),
        ], coins[:-1]))

        final_coin_creation += [
            [CONDITION_CREATE_COIN_ANNOUNCEMENT, final_coin.name()],
            [CONDITION_CREATE_COIN, self.puzzle_hash, final_coin.amount],
        ]

        coin_solution, signature = coins[-1].create_standard_spend(self.priv_, final_coin_creation)
        destroyed_coin_solutions.append(coin_solution)
        signatures.append(signature)

        signature = AugSchemeMPL.aggregate(signatures)
        spend_bundle = SpendBundle(destroyed_coin_solutions, signature)

        pushed = self.parent.push_tx(spend_bundle)

        # We should have the same amount of money.
        assert beginning_balance == self.balance()
        # We should have shredded n-1 coins and replaced one.
        assert len(self.usable_coins) == beginning_coins - (len(coins) - 1)

        return SpendResult(pushed)

    # Find a coin containing amt we can use as a parent.
    # Synthesize a coin with sufficient funds if possible.
    def choose_coin(self,amt) -> CoinWrapper:
        """Given an amount requirement, find a coin that contains at least that much chia"""
        best_fit_coin = None
        for _ in range(1000):
            for k,c in self.usable_coins.items():
                if best_fit_coin is None and c.amount >= amt:
                    best_fit_coin = c
                elif c.amount >= amt and c.amount < best_fit_coin.amount:
                    best_fit_coin = c
                else:
                    pass

            if best_fit_coin is not None:
                return best_fit_coin

            actions_to_take = self.compute_combine_action(amt, [], dict(self.usable_coins))
            # Couldn't find a working combination.
            if actions_to_take is None:
                return None

            # We receive a timeline of actions to take (indicating that we have a plan)
            # Do the first action and start over.
            result = self.combine_coins(
                list(
                    map(
                        lambda x:CoinWrapper(
                            x.parent_coin_info,
                            x.puzzle_hash,
                            x.amount,
                            self.puzzle
                        ),
                        actions_to_take[0]
                    )
                )
            )

            # Bugged out, couldn't combine for some reason.
            if result is None:
                return None

    # Create a new contract based on a parent coin and return the coin to the user.
    # TODO:
    #  - allow use of more than one coin to launch contract
    #  - ensure input chia = output chia.  it'd be dumb to just allow somebody
    #    to lose their chia without telling them.
    def launch_contract(self,source,**kwargs) -> CoinWrapper:
        """Create a new contract based on a parent coin and return the contract's living
        coin to the user or None if the spend failed."""
        amt = 1
        if 'amt' in kwargs:
            amt = kwargs['amt']

        found_coin = self.choose_coin(amt)
        if found_coin is None:
            raise ValueError(f'could not find available coin containing {amt} mojo')

        # Create a puzzle based on the incoming contract
        cw = ContractWrapper(DEFAULT_CONSTANTS.GENESIS_CHALLENGE, source)
        condition_args = [
            [ConditionOpcode.CREATE_COIN, cw.puzzle_hash(), amt],
        ]
        if amt < found_coin.amount:
            condition_args.append(
                [ConditionOpcode.CREATE_COIN, self.puzzle_hash, found_coin.amount - amt]
            )

        delegated_puzzle_solution = Program.to((1, condition_args))
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
        if 'error' not in pushed:
            return cw.custom_coin(found_coin, amt)
        else:
            return None

    # Give chia
    def give_chia(self, target, amt):
        return self.launch_contract(target.puzzle, amt=amt)

    # Called each cycle before coins are re-established from the simulator.
    def _clear_coins(self):
        self.usable_coins = {}

    # Public key of wallet
    def pk(self):
        """Return actor's public key"""
        return self.pk_

    # Balance of wallet
    def balance(self):
        """Return the actor's balance in standard coins as we understand it"""
        return sum(map(lambda x: x.amount, self.usable_coins.values()))

    # Spend a coin, probably a contract coin.
    # Allows the user to specify the arguments for the puzzle solution.
    # Automatically takes care of signing, etc.
    # Result is an object representing the actions taken when the block
    # with this transaction was farmed.
    def spend_coin(self, coin : CoinWrapper, **kwargs):
        """Given a coin object, invoke it on the blockchain, either as a standard
        coin if no arguments are given or with custom arguments in args="""
        amt = 1
        if 'amt' in kwargs:
            amt = kwargs['amt']

        def pk_to_sk(pk: G1Element) -> PrivateKey:
            assert pk == self.pk()
            return self.priv_

        delegated_puzzle_solution = None
        if not 'args' in kwargs:
            target_puzzle_hash = self.puzzle_hash
            # Allow the user to 'give this much chia' to another user.
            if 'to' in kwargs:
                target_puzzle_hash = kwargs['to'].puzzle_hash

            # Automatic arguments from the user's intention.
            solution_list = [[ConditionOpcode.CREATE_COIN, target_puzzle_hash, amt]]
            if 'remain' in kwargs:
                remainer = kwargs['remain']
                remain_amt = coin.amount - amt
                if isinstance(remainer, ContractWrapper):
                    solution_list.append([ConditionOpcode.CREATE_COIN, remainer.puzzle_hash(), remain_amt])
                elif isinstance(remainer, Wallet):
                    solution_list.append([ConditionOpcode.CREATE_COIN, remainer.puzzle_hash, remain_amt])
                else:
                    raise ValueError("remainer is not a waller or a contract")

            delegated_puzzle_solution = Program.to((1, solution_list))
            # Solution is the solution for the old coin.
            solution = Program.to([[], delegated_puzzle_solution, []])
        else:
            delegated_puzzle_solution = Program.to(kwargs['args'])
            solution = delegated_puzzle_solution

        solution_for_coin = CoinSolution(
            coin,
            coin.puzzle(),
            solution,
        )

        # Sign the (delegated_puzzle_hash + coin_name) with synthetic secret key
        signature = AugSchemeMPL.sign(
            calculate_synthetic_secret_key(self.priv_,DEFAULT_HIDDEN_PUZZLE_HASH),
            (delegated_puzzle_solution.get_tree_hash() + coin.name() + DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA)
        )

        spend_bundle = sign_coin_solutions(
            [solution_for_coin],
            pk_to_sk,
            DEFAULT_CONSTANTS.AGG_SIG_ME_ADDITIONAL_DATA,
            DEFAULT_CONSTANTS.MAX_BLOCK_COST_CLVM
        )

        pushed = self.parent.push_tx(SpendBundle.from_chia_spend_bundle(spend_bundle))
        return SpendResult(pushed)

# A user oriented (domain specific) view of the chia network.
class Network:
    """An object that owns a node simulation, responsible for managing Wallet actors,
    time and initialization."""
    def __init__(self):
        self.wallets = {}
        self.time = datetime.timedelta(0)
        self.node = Node()
        self.node.set_timestamp(0.01)
        self.nobody = self.make_wallet('nobody')
        self.wallets[str(self.nobody.pk())] = self.nobody

    # Have the system farm one block with a specific beneficiary (nobody if not specified).
    def farm_block(self,**kwargs):
        """Given a farmer, farm a block with that actor as the beneficiary of the farm
        reward.

        Used for causing chia balance to exist so the system can do things.
        """
        farmer = self.nobody
        if 'farmer' in kwargs:
            farmer = kwargs['farmer']

        farm_duration = datetime.timedelta(block_time)
        farmed = self.node.farm_block(farmer.pk())

        for k, w in self.wallets.items():
            w._clear_coins()

        for coin in self.node.coins:
            for kw, w in self.wallets.items():
                if coin.puzzle_hash == w.puzzle_hash:
                    w.add_coin(coin)

        self.time += farm_duration
        return farmed

    def _alloc_key(self):
        key_idx = len(self.wallets)
        pk = public_key_for_index(key_idx)
        priv = private_key_for_index(key_idx)
        return pk, priv

    # Allow the user to create a wallet identity to whom standard coins may be targeted.
    # This results in the creation of a wallet that tracks balance and standard coins.
    # Public and private key from here are used in signing.
    def make_wallet(self,name):
        """Create a wallet for an actor.  This causes the actor's chia balance in standard
        coin to be tracked during the simulation.  Wallets have some domain specific methods
        that behave in similar ways to other blockchains."""
        pk, priv = self._alloc_key()
        w = Wallet(self, name, pk, priv)
        self.wallets[str(w.pk())] = w
        return w

    # Skip real time by farming blocks until the target duration is achieved.
    def skip_time(self,t,**kwargs):
        """Skip a duration of simulated time, causing blocks to be farmed.  If a farmer
        is specified, they win each block"""
        target_duration = pytimeparse.parse(t)
        target_time = self.time + datetime.timedelta(target_duration / duration_div)
        while target_time > self.get_timestamp():
            self.farm_block(**kwargs)

        # Or possibly aggregate farm_block results.
        return None

    def get_timestamp(self):
        """Return the current simualtion time in seconds."""
        return datetime.timedelta(seconds = self.node.timestamp)

    # Given a spend bundle, farm a block and analyze the result.
    def push_tx(self,bundle,more=False):
        """Given a spend bundle, try to farm a block containing it.  If the spend bundle
        didn't validate, then a result containing an 'error' key is returned.  The reward
        for the block goes to Network::nobody"""
        try:
            res = self.node.push_tx(bundle)
        except ValueError as e:
            return { "error": str(e) }

        if not more:
            # Common case that we want to farm this right away.
            results = self.farm_block()
            return {
                'cost': res['cost'],
                'additions': results['additions'],
                'removals': results['removals']
            }
        else:
            return {'cost': 0, 'additions':[], 'removals': []}

class TestGroup(TestCase):
    def setUp(self):
        self.coin_multiple = 1000000000000
        self.network = Network()
        self.network.farm_block() # gives 21000000 chia!

    def __init__(self,t):
        super().__init__(t)
