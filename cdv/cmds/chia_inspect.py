import click
import json

from pprint import pprint

from blspy import AugSchemeMPL, G2Element

from chia.types.blockchain_format.program import INFINITE_COST, Program
from chia.types.blockchain_format.coin import Coin
from chia.types.coin_spend import CoinSpend
from chia.types.coin_record import CoinRecord
from chia.types.spend_bundle import SpendBundle
from chia.consensus.cost_calculator import calculate_cost_of_program
from chia.full_node.mempool_check_conditions import get_name_puzzle_conditions
from chia.full_node.bundle_tools import simple_solution_generator
from chia.util.ints import uint64
from chia.util.condition_tools import conditions_dict_for_solution, pkm_pairs_for_conditions_dict

from cdv.cmds.clsp import parse_program

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
    if not any([value for key, value in ctx.obj.items()]):
        if getattr(objs[0], "to_json_dict", None):
            pprint([obj.to_json_dict() for obj in objs])
        else:
            pprint(f"Object of type {type} cannot be serialized to JSON")
    else:
        if ctx.obj['json']:
            if getattr(obj, "to_json_dict", None):
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
def sanitize_bytes(bytecode):
    return bytecode[2:] if bytecode[:2] == "0x" else bytecode

def fake_context():
    ctx = {}
    ctx["obj"] = {"json": True}
    return ctx

def json_and_key_strip(input):
    json_dict = json.loads(input)
    if len(json_dict.keys()) == 1:
        return json_dict[json_dict.keys()[0]]
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
                input_objs.append(cls.from_bytes(bytes.fromhex(file_string)))
        else:
            input_objs.append(cls.from_bytes(bytes.fromhex(input)))

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
        coin_objs = [Coin(bytes.fromhex(kwargs['parent_id']), bytes.fromhex(kwargs['puzzle_hash']), uint64(kwargs['amount']))]
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
        inspect_callback(coin_objs, ctx, id_calc=(lambda e: e.name()), type='Coin')
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
                    bytes.fromhex(kwargs['parent_id']),
                    bytes.fromhex(kwargs['puzzle_hash']),
                    uint64(kwargs['amount']),
                ),
                parse_program(sanitize_bytes(kwargs['puzzle_reveal'])),
                parse_program(sanitize_bytes(kwargs['solution'])),
            )]
        elif kwargs['coin']:
            coin_spend_objs = [CoinSpend(
                do_inspect_coin_cmd(ctx, [kwargs['coin']], print_results=False)[0],
                parse_program(sanitize_bytes(kwargs['puzzle_reveal'])),
                parse_program(sanitize_bytes(kwargs['solution'])),
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
        inspect_callback(coin_spend_objs, ctx, id_calc=(lambda e: e.coin.name()), type='CoinSpend')
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
@click.option("-ec","--cost", is_flag=True, help="Print the CLVM cost of the spend")
@click.option("-bc","--cost-per-byte", default=12000, show_default=True, help="The cost per byte in the puzzle and solution reveal to use when calculating cost")
@click.pass_context
def inspect_spend_bundle_cmd(ctx, bundles, **kwargs):
    do_inspect_spend_bundle_cmd(ctx, bundles, **kwargs)

def do_inspect_spend_bundle_cmd(ctx, bundles, print_results=True, **kwargs):
    if kwargs and (len(kwargs['spend']) > 0):
        if (len(kwargs['aggsig']) > 0):
            sig = AugSchemeMPL.aggregate([G2Element(bytes.fromhex(sanitize_bytes(sig))) for sig in kwargs["aggsig"]])
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
        inspect_callback(spend_bundle_objs, ctx, id_calc=(lambda e: e.name()), type='SpendBundle')
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
                            pkm_dict = {}
                            for pk, msg in pkm_pairs_for_conditions_dict(
                                conditions_dict,
                                coin_spend.coin.name(),
                                bytes.fromhex(genesis_challenge),
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
                    bytes.fromhex(kwargs['parent_id']),
                    bytes.fromhex(kwargs['puzzle_hash']),
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
        inspect_callback(coin_record_objs, ctx, id_calc=(lambda e: e.coin.name()), type='CoinRecord')
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
        inspect_callback(program_objs, ctx, id_calc=(lambda e: e.get_tree_hash()), type='Program')
    else:
        return program_objs
