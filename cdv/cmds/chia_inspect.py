import click
import json

from pprint import pprint
from secrets import token_bytes

from blspy import AugSchemeMPL, PrivateKey, G1Element, G2Element

from chia.types.blockchain_format.program import INFINITE_COST, Program
from chia.types.blockchain_format.coin import Coin
from chia.types.coin_spend import CoinSpend
from chia.types.coin_record import CoinRecord
from chia.types.spend_bundle import SpendBundle
from chia.consensus.cost_calculator import calculate_cost_of_program
from chia.full_node.mempool_check_conditions import get_name_puzzle_conditions
from chia.full_node.bundle_tools import simple_solution_generator
from chia.wallet.derive_keys import _derive_path
from chia.wallet.puzzles.p2_delegated_puzzle_or_hidden_puzzle import (
    DEFAULT_HIDDEN_PUZZLE_HASH,
    calculate_synthetic_secret_key,
    calculate_synthetic_public_key,
)
from chia.util.keychain import mnemonic_to_seed, bytes_to_mnemonic
from chia.util.ints import uint64, uint32
from chia.util.condition_tools import conditions_dict_for_solution, pkm_pairs_for_conditions_dict
from chia.util.byte_types import hexstr_to_bytes

from cdv.cmds.util import parse_program

@click.group("inspect", short_help="Inspect various data structures")
@click.option("-j","--json", is_flag=True, help="Output the result as JSON")
@click.option("-b","--bytes", is_flag=True, help="Output the result as bytes")
@click.option("-id","--id", is_flag=True, help="Output the id of the object")
@click.option("-t","--type", is_flag=True, help="Output the type of the object")
@click.pass_context
def inspect_cmd(ctx, **kwargs):
    ctx.ensure_object(dict)
    for key, value in kwargs.items():
        ctx.obj[key] = value

def inspect_callback(objs, ctx, id_calc=None, type='Unknown'):
    if (not any([value for key, value in ctx.obj.items()])) or ctx.obj['json']:
        if getattr(objs[0], "to_json_dict", None):
            pprint([obj.to_json_dict() for obj in objs])
        else:
            pprint(f"Object of type {type} cannot be serialized to JSON")
    if ctx.obj['bytes']:
        final_output = []
        for obj in objs:
            try:
                final_output.append(bytes(obj).hex())
            except AssertionError:
                final_output.append(None)
        pprint(final_output)
    if ctx.obj['id']:
        pprint([id_calc(obj) for obj in objs])
    if ctx.obj['type']:
        pprint([type for _ in objs])

# Utility functions
def json_and_key_strip(input):
    json_dict = json.loads(input)
    if len(json_dict.keys()) == 1:
        return json_dict[list(json_dict.keys())[0]]
    else:
        return json_dict

def streamable_load(cls, inputs):
    input_objs = []
    for input in inputs:
        if "{" in input:
            input_objs.append(cls.from_json_dict(json_and_key_strip(input)))
        elif "." in input:
            file_string = open(input, "r").read()
            if "{" in file_string:
                input_objs.append(cls.from_json_dict(json_and_key_strip(file_string)))
            else:
                input_objs.append(cls.from_bytes(hexstr_to_bytes(file_string)))
        else:
            input_objs.append(cls.from_bytes(hexstr_to_bytes(input)))

    return input_objs

@inspect_cmd.command("any", short_help="Attempt to guess the type of the object before inspecting it")
@click.argument("objects", nargs=-1, required=False)
@click.pass_context
def inspect_any_cmd(ctx, objects):
    input_objects = []
    for obj in objects:
        in_obj = obj
        # Try it as Streamable types
        for cls in [Coin, CoinSpend, SpendBundle, CoinRecord]:
            try:
                in_obj = streamable_load(cls, [obj])[0]
            except:
                pass
        # Try it as some key stuff
        for cls in [G1Element, G2Element, PrivateKey]:
            try:
                in_obj = cls.from_bytes(hexstr_to_bytes(obj))
            except:
                pass
        # Try it as a Program
        try:
            in_obj = parse_program(obj)
        except:
            pass

        input_objects.append(in_obj)

    for obj in input_objects:
        if type(obj) == str:
            print(f"Could not guess the type of {obj}")
        elif type(obj) == Coin:
            do_inspect_coin_cmd(ctx, [obj])
        elif type(obj) == CoinSpend:
            do_inspect_coin_spend_cmd(ctx, [obj])
        elif type(obj) == SpendBundle:
            do_inspect_spend_bundle_cmd(ctx, [obj])
        elif type(obj) == CoinRecord:
            do_inspect_coin_record_cmd(ctx, [obj])
        elif type(obj) == Program:
            do_inspect_program_cmd(ctx, [obj])
        elif type(obj) == G1Element:
            do_inspect_keys_cmd(ctx, public_key=obj)
        elif type(obj) == PrivateKey:
            do_inspect_keys_cmd(ctx, secret_key=obj)
        elif type(obj) == G2Element:
            print("That's a BLS aggregated signature")


@inspect_cmd.command("coins", short_help="Various methods for examining and calculating coin objects")
@click.argument("coins", nargs=-1, required=False)
@click.option("-pid","--parent-id", help="The parent coin's ID")
@click.option("-ph","--puzzle-hash", help="The tree hash of the CLVM puzzle that locks this coin")
@click.option("-a","--amount", help="The amount of the coin")
@click.pass_context
def inspect_coin_cmd(ctx, coins, **kwargs):
    do_inspect_coin_cmd(ctx, coins, **kwargs)

def do_inspect_coin_cmd(ctx, coins, print_results=True, **kwargs):
    if kwargs and all([kwargs[key] for key in kwargs.keys()]):
        coin_objs = [Coin(hexstr_to_bytes(kwargs['parent_id']), hexstr_to_bytes(kwargs['puzzle_hash']), uint64(kwargs['amount']))]
    elif not kwargs or not any([kwargs[key] for key in kwargs.keys()]):
        coin_objs = []
        try:
            if type(coins[0]) == str:
                coin_objs = streamable_load(Coin, coins)
            else:
                coin_objs = coins
        except:
            print("One or more of the specified objects was not a coin")
    else:
        print("Invalid arguments specified.")
        return

    if print_results:
        inspect_callback(coin_objs, ctx, id_calc=(lambda e: e.name().hex()), type='Coin')
    else:
        return coin_objs

@inspect_cmd.command("spends", short_help="Various methods for examining and calculating CoinSpend objects")
@click.argument("spends", nargs=-1, required=False)
@click.option("-c","--coin", help="The coin to spend (replaces -pid, -ph, -a)")
@click.option("-pid","--parent-id", help="The parent coin's ID")
@click.option("-ph","--puzzle-hash", help="The tree hash of the CLVM puzzle that locks the coin being spent")
@click.option("-a","--amount", help="The amount of the coin being spent")
@click.option("-pr","--puzzle-reveal", help="The program that is hashed into this coin")
@click.option("-s","--solution", help="The attempted solution to the puzzle")
@click.option("-ec","--cost", is_flag=True, help="Print the CLVM cost of the spend")
@click.option("-bc","--cost-per-byte", default=12000, show_default=True, help="The cost per byte in the puzzle and solution reveal to use when calculating cost")
@click.pass_context
def inspect_coin_cmd(ctx, spends, **kwargs):
    do_inspect_coin_spend_cmd(ctx, spends, **kwargs)

def do_inspect_coin_spend_cmd(ctx, spends, print_results=True, **kwargs):
    cost_flag = False
    cost_per_byte = 12000
    if kwargs:
        cost_flag = kwargs["cost"]
        cost_per_byte = kwargs["cost_per_byte"]
        del kwargs["cost"]
        del kwargs["cost_per_byte"]
    if kwargs and all([kwargs['puzzle_reveal'], kwargs['solution']]):
        if (not kwargs['coin']) and all([kwargs['parent_id'], kwargs['puzzle_hash'], kwargs['amount']]):
            coin_spend_objs = [CoinSpend(
                Coin(
                    hexstr_to_bytes(kwargs['parent_id']),
                    hexstr_to_bytes(kwargs['puzzle_hash']),
                    uint64(kwargs['amount']),
                ),
                parse_program(kwargs['puzzle_reveal']),
                parse_program(kwargs['solution']),
            )]
        elif kwargs['coin']:
            coin_spend_objs = [CoinSpend(
                do_inspect_coin_cmd(ctx, [kwargs['coin']], print_results=False)[0],
                parse_program(kwargs['puzzle_reveal']),
                parse_program(kwargs['solution']),
            )]
        else:
            print("Invalid arguments specified.")
    elif not kwargs or not any([kwargs[key] for key in kwargs.keys()]):
        coin_spend_objs = []
        try:
            if type(spends[0]) == str:
                coin_spend_objs = streamable_load(CoinSpend, spends)
            else:
                coin_spend_objs = spends
        except:
            print("One or more of the specified objects was not a coin spend")
    else:
        print("Invalid arguments specified.")
        return

    if print_results:
        inspect_callback(coin_spend_objs, ctx, id_calc=(lambda e: e.coin.name().hex()), type='CoinSpend')
        if cost_flag:
            for coin_spend in coin_spend_objs:
                program = simple_solution_generator(SpendBundle([coin_spend], G2Element()))
                npc_result = get_name_puzzle_conditions(program, INFINITE_COST, cost_per_byte=cost_per_byte, safe_mode=True)
                cost = calculate_cost_of_program(program, npc_result, cost_per_byte)
                print(f"Cost: {cost}")
    else:
        return coin_spend_objs

@inspect_cmd.command("spendbundles", short_help="Various methods for examining and calculating SpendBundle objects")
@click.argument("bundles", nargs=-1, required=False)
@click.option("-s","--spend", multiple=True, help="A coin spend object to add to the bundle")
@click.option("-as","--aggsig", multiple=True, help="A BLS signature to aggregate into the bundle (can be used more than once)")
@click.option("-db","--debug", is_flag=True, help="Show debugging information about the bundles")
@click.option("-sd","--signable_data", is_flag=True, help="Print the data that needs to be signed in the bundles")
@click.option("-n","--network", default="mainnet", show_default=True, help="The network this spend bundle will be pushed to (for AGG_SIG_ME)")
@click.option("-ec","--cost", is_flag=True, help="Print the CLVM cost of the entire bundle")
@click.option("-bc","--cost-per-byte", default=12000, show_default=True, help="The cost per byte in the puzzle and solution reveal to use when calculating cost")
@click.pass_context
def inspect_spend_bundle_cmd(ctx, bundles, **kwargs):
    do_inspect_spend_bundle_cmd(ctx, bundles, **kwargs)

def do_inspect_spend_bundle_cmd(ctx, bundles, print_results=True, **kwargs):
    if kwargs and (len(kwargs['spend']) > 0):
        if (len(kwargs['aggsig']) > 0):
            sig = AugSchemeMPL.aggregate([G2Element(hexstr_to_bytes(sig)) for sig in kwargs["aggsig"]])
        else:
            sig = G2Element()
        spend_bundle_objs = [SpendBundle(
            do_inspect_coin_spend_cmd(ctx, kwargs["spend"], print_results=False),
            sig
        )]
    else:
        spend_bundle_objs = []
        try:
            if type(bundles[0]) == str:
                spend_bundle_objs = streamable_load(SpendBundle, bundles)
            else:
                spend_bundle_objs = bundles
        except:
            print("One or more of the specified objects was not a spend bundle")

    if print_results:
        inspect_callback(spend_bundle_objs, ctx, id_calc=(lambda e: e.name().hex()), type='SpendBundle')
        if kwargs:
            if kwargs["cost"]:
                for spend_bundle in spend_bundle_objs:
                    program = simple_solution_generator(spend_bundle)
                    npc_result = get_name_puzzle_conditions(program, INFINITE_COST, cost_per_byte=kwargs["cost_per_byte"], safe_mode=True)
                    cost = calculate_cost_of_program(program, npc_result, kwargs["cost_per_byte"])
                    print(f"Cost: {cost}")
            if kwargs["debug"]:
                print(f"")
                print(f"Debugging Information")
                print(f"---------------------")
                for bundle in spend_bundle_objs:
                    print(bundle.debug())
            if kwargs["signable_data"]:
                print(f"")
                print(f"Public Key/Message Pairs")
                print(f"------------------------")
                pkm_dict = {}
                for obj in spend_bundle_objs:
                    for coin_spend in obj.coin_spends:
                        err, conditions_dict, _ = conditions_dict_for_solution(
                            coin_spend.puzzle_reveal, coin_spend.solution, INFINITE_COST
                        )
                        if err or conditions_dict is None:
                            print(f"Generating conditions failed, con:{conditions_dict}, error: {err}")
                        else:
                            from chia.util.default_root import DEFAULT_ROOT_PATH
                            from chia.util.config import load_config
                            config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
                            genesis_challenge = config["network_overrides"]["constants"][kwargs["network"]]["GENESIS_CHALLENGE"]
                            for pk, msg in pkm_pairs_for_conditions_dict(
                                conditions_dict,
                                coin_spend.coin.name(),
                                hexstr_to_bytes(genesis_challenge),
                            ):
                                if str(pk) in pkm_dict:
                                    pkm_dict[str(pk)].append(msg)
                                else:
                                    pkm_dict[str(pk)] = [msg]
                for pk, msgs in pkm_dict.items():
                    print(f"{pk}:")
                    for msg in msgs:
                        print(f"\t- {msg.hex()}")
    else:
        return spend_bundle_objs

@inspect_cmd.command("coinrecords", short_help="Various methods for examining and calculating CoinRecord objects")
@click.argument("records", nargs=-1, required=False)
@click.option("-c","--coin", help="The coin to spend (replaces -pid, -ph, -a)")
@click.option("-pid","--parent-id", help="The parent coin's ID")
@click.option("-ph","--puzzle-hash", help="The tree hash of the CLVM puzzle that locks the coin being spent")
@click.option("-a","--amount", help="The amount of the coin being spent")
@click.option("-cb","--coinbase", is_flag=True, help="Is this coin generated as a farming reward?")
@click.option("-ci","--confirmed-block-index", help="The block index in which this coin was created")
@click.option("-s","--spent", is_flag=True, help="Has the coin been spent?")
@click.option("-si","--spent-block-index", default=0, show_default=True, type=int, help="The block index in which this coin was spent")
@click.option("-t","--timestamp", help="The timestamp of the block in which this coin was created")
@click.pass_context
def inspect_coin_record_cmd(ctx, records, **kwargs):
    do_inspect_coin_record_cmd(ctx, records, **kwargs)

def do_inspect_coin_record_cmd(ctx, records, print_results=True, **kwargs):
    if kwargs and all([kwargs['confirmed_block_index'], kwargs['timestamp']]):
        if (not kwargs['coin']) and all([kwargs['parent_id'], kwargs['puzzle_hash'], kwargs['amount']]):
            coin_record_objs = [CoinRecord(
                Coin(
                    hexstr_to_bytes(kwargs['parent_id']),
                    hexstr_to_bytes(kwargs['puzzle_hash']),
                    uint64(kwargs['amount']),
                ),
                kwargs["confirmed_block_index"],
                kwargs["spent_block_index"],
                kwargs["spent"],
                kwargs["coinbase"],
                kwargs["timestamp"],
            )]
        elif kwargs['coin']:
            coin_record_objs = [CoinRecord(
                do_inspect_coin_cmd(ctx, [kwargs['coin']], print_results=False)[0],
                kwargs["confirmed_block_index"],
                kwargs["spent_block_index"],
                kwargs["spent"],
                kwargs["coinbase"],
                kwargs["timestamp"],
            )]
        else:
            print("Invalid arguments specified.")
    elif not kwargs or not any([kwargs[key] for key in kwargs.keys()]):
        coin_record_objs = []
        try:
            if type(records[0]) == str:
                coin_record_objs = streamable_load(CoinRecord, records)
            else:
                coin_record_objs = records
        except:
            print("One or more of the specified objects was not a coin record")
    else:
        print("Invalid arguments specified.")
        return

    if print_results:
        inspect_callback(coin_record_objs, ctx, id_calc=(lambda e: e.coin.name().hex()), type='CoinRecord')
    else:
        return coin_record_objs

@inspect_cmd.command("programs", short_help="Various methods for examining CLVM Program objects")
@click.argument("programs", nargs=-1, required=False)
@click.pass_context
def inspect_program_cmd(ctx, programs, **kwargs):
    do_inspect_program_cmd(ctx, programs, **kwargs)

def do_inspect_program_cmd(ctx, programs, print_results=True, **kwargs):
    program_objs = []
    try:
        if type(programs[0]) == str:
            program_objs = [parse_program(prog) for prog in programs]
        else:
            program_objs = programs
    except:
        print("One or more of the specified objects was not a Program")

    if print_results:
        inspect_callback(program_objs, ctx, id_calc=(lambda e: e.get_tree_hash().hex()), type='Program')
    else:
        return program_objs

@inspect_cmd.command("keys", short_help="Various methods for examining and generating BLS Keys")
@click.option("-pk","--public-key", help="A BLS public key")
@click.option("-sk","--secret-key", help="The secret key from which to derive the public key")
@click.option("-m","--mnemonic", help="A 24 word mnemonic from which to derive the secret key")
@click.option("-pw","--passphrase", default="", show_default=True, help="A passphrase to use when deriving a secret key from mnemonic")
@click.option("-r","--random", is_flag=True, help="Generate a random set of keys")
@click.option("-hd","--hd-path", help="Enter the HD path in the form 'm/12381/8444/n/n'")
@click.option("-t","--key-type", type=click.Choice(["farmer","pool","wallet","local","backup","owner","auth"]), help="Automatically use a chia defined HD path for a specific service")
@click.option("-sy","--synthetic", is_flag=True, help="Use a hidden puzzle hash (-ph) to calculate a synthetic secret/public key")
@click.option("-ph","--hidden-puzhash", default=DEFAULT_HIDDEN_PUZZLE_HASH.hex(), show_default=False, help="The hidden puzzle to use when calculating a synthetic key")
@click.pass_context
def inspect_keys_cmd(ctx, **kwargs):
    do_inspect_keys_cmd(ctx, **kwargs)

def do_inspect_keys_cmd(ctx, print_results=True, **kwargs):
    sk = None
    pk = None
    path = "m"
    if len(kwargs) == 1:
        if "secret_key" in kwargs:
            sk = kwargs["secret_key"]
            pk = sk.get_g1()
        elif "public_key" in kwargs:
            pk = kwargs["public_key"]
    else:
        condition_list = [kwargs["public_key"], kwargs["secret_key"], kwargs["mnemonic"], kwargs["random"]]
        def one_or_zero(value):
            return 1 if value else 0
        if sum([one_or_zero(condition) for condition in condition_list]) == 1:
            if kwargs["public_key"]:
                sk = None
                pk = G1Element.from_bytes(hexstr_to_bytes(kwargs["public_key"]))
            elif kwargs["secret_key"]:
                sk = PrivateKey.from_bytes(hexstr_to_bytes(kwargs["secret_key"]))
                pk = sk.get_g1()
            elif kwargs["mnemonic"]:
                seed = mnemonic_to_seed(kwargs["mnemonic"], kwargs["passphrase"])
                sk = AugSchemeMPL.key_gen(seed)
                pk = sk.get_g1()
            elif kwargs["random"]:
                sk = AugSchemeMPL.key_gen(mnemonic_to_seed(bytes_to_mnemonic(token_bytes(32)),""))
                pk = sk.get_g1()

            if kwargs["hd_path"] and (kwargs["hd_path"] != "m"):
                path = [uint32(int(i)) for i in kwargs["hd_path"].split("/") if i != "m"]
            elif kwargs["key_type"]:
                case = kwargs["key_type"]
                if case == "farmer":
                    path = [12381, 8444, 0, 0]
                if case == "pool":
                    path = [12381, 8444, 1, 0]
                if case == "wallet":
                    path = [12381, 8444, 2, 0]
                if case == "local":
                    path = [12381, 8444, 3, 0]
                if case == "backup":
                    path = [12381, 8444, 4, 0]
                if case == "owner":
                    path = [12381, 8444, 5, 0]
                if case == "auth":
                    path = [12381, 8444, 6, 0]
            if path != "m":
                sk = _derive_path(sk, path)
                pk = sk.get_g1()
                path = "m/" + "/".join([str(e) for e in path])

            if kwargs["synthetic"]:
                if sk:
                    sk = calculate_synthetic_secret_key(sk, hexstr_to_bytes(kwargs["hidden_puzhash"]))
                pk = calculate_synthetic_public_key(pk, hexstr_to_bytes(kwargs["hidden_puzhash"]))
        else:
            print("Invalid arguments specified.")

    if sk:
        print(f"Secret Key: {bytes(sk).hex()}")
    print(f"Public Key: {str(pk)}")
    print(f"Fingerprint: {str(pk.get_fingerprint())}")
    print(f"HD Path: {path}")


class OrderedParamsCommand(click.Command):
    _options = []

    def parse_args(self, ctx, args):
        # run the parser for ourselves to preserve the passed order
        parser = self.make_parser(ctx)
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            if param.name != "help":
                type(self)._options.append((param, opts[param.name].pop(0)))

        # return "normal" parse results
        return super().parse_args(ctx, args)

@inspect_cmd.command("signatures", cls=OrderedParamsCommand, short_help="Various methods for examining and creating BLS aggregated signatures")
@click.option("-sk","--secret-key", multiple=True, help="A secret key to sign a message with")
@click.option("-t","--utf-8", multiple=True, help="A UTF-8 message to be signed with the specified secret key")
@click.option("-b","--bytes", multiple=True, help="A hex message to be signed with the specified secret key")
@click.option("-sig","--aggsig", multiple=True, help="A signature to be aggregated")
@click.pass_context
def inspect_sigs_cmd(ctx, **kwargs):
    do_inspect_sigs_cmd(ctx, **kwargs)

def do_inspect_sigs_cmd(ctx, print_results=True, **kwargs):
    base = G2Element()
    sk = None
    for param, value in OrderedParamsCommand._options:
        if param.name == "secret_key":
            sk = PrivateKey.from_bytes(hexstr_to_bytes(value))
        elif param.name == "aggsig":
            new_sig = G2Element.from_bytes(hexstr_to_bytes(value))
            base = AugSchemeMPL.aggregate([base, new_sig])
        elif sk:
            if param.name == "utf_8":
                new_sig = AugSchemeMPL.sign(sk, bytes(value, "utf-8"))
                base = AugSchemeMPL.aggregate([base, new_sig])
            if param.name == "bytes":
                new_sig = AugSchemeMPL.sign(sk, hexstr_to_bytes(value))
                base = AugSchemeMPL.aggregate([base, new_sig])

    if print_results:
        print(str(base))
    else:
        return base
