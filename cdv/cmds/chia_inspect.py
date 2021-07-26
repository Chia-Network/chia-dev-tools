import click
import json

from pprint import pprint

from blspy import AugSchemeMPL, G2Element

from chia.types.blockchain_format.coin import Coin
from chia.types.coin_spend import CoinSpend
from chia.types.spend_bundle import SpendBundle
from chia.util.ints import uint64

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
        pprint([obj.to_json_dict() for obj in objs])
    else:
        if ctx.obj['json']:
            pprint([obj.to_json_dict() for obj in objs])
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
        for cls in [Coin, CoinSpend, SpendBundle]:
            try:
                in_obj = streamable_load(cls, [obj])[0]
            except Exception as e:
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
@click.pass_context
def inspect_coin_cmd(ctx, spends, **kwargs):
    do_inspect_coin_spend_cmd(ctx, spends, **kwargs)

def do_inspect_coin_spend_cmd(ctx, spends, print_results=True, **kwargs):
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
    else:
        return coin_spend_objs

@inspect_cmd.command("spendbundles", short_help="Various methods for examining and calculating SpendBundle objects")
@click.argument("bundles", nargs=-1, required=False)
@click.option("-s","--spend", multiple=True, help="A coin spend object to add to the bundle")
@click.option("-as","--aggsig", multiple=True, help="A BLS signature to aggregate into the bundle (can be used more than once)")
@click.pass_context
def inspect_spend_bundle_cmd(ctx, bundles, **kwargs):
    do_inspect_spend_bundle_cmd(ctx, bundles, **kwargs)

def do_inspect_spend_bundle_cmd(ctx, bundles, print_results=True, **kwargs):
    if kwargs and (len(kwargs['spend']) > 0) and (len(kwargs['aggsig']) > 0):
        spend_bundle_objs = [SpendBundle(
            do_inspect_coin_spend_cmd(ctx, kwargs["spend"], print_results=False),
            AugSchemeMPL.aggregate([G2Element(bytes.fromhex(sanitize_bytes(aggsig))) for aggsig in kwargs["aggsig"]])
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
    else:
        return spend_bundle_objs