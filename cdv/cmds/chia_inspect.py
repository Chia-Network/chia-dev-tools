import click
import json

from chia.types.blockchain_format.coin import Coin
from pprint import pprint

@click.group("inspect", short_help="Inspect various data structures")
@click.option("-j","--json", is_flag=True, help="Output the result as JSON")
@click.option("-b","--bytes", is_flag=True, help="Output the result as bytes")
@click.option("--id", is_flag=True, help="Output the id of the object")
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
                    final_output.append(bytes(obj))
                except AssertionError:
                    final_output.append(None)
            pprint(final_output)
        if ctx.obj['id']:
            pprint([id_calc(obj) for obj in objs])
        if ctx.obj['type']:
            pprint([type for _ in objs])

def streamable_load(cls, inputs):
    input_objs = []
    for input in inputs:
        if "{" in input:
            input_objs.append(cls.from_json_dict(json.loads(input)))
        elif "." in input:
            file_string = open(input, "r").read()
            if "{" in file_string:
                input_objs.append(cls.from_json_dict(json.loads(file_string)))
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
        for cls in [Coin]:
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


@inspect_cmd.command("coins", short_help="Various methods for examining and calculating coin objects")
@click.argument("coins", nargs=-1, required=True)
@click.option("-pid","--parent-id", help="The parent coin's ID")
@click.option("-ph","--puzzle-hash", help="The tree hash of the CLVM puzzle that locks this coin")
@click.option("-a","--amount", help="The amount of the coin")
@click.pass_context
def inspect_coin_cmd(ctx, coins, **kwargs):
    do_inspect_coin_cmd(ctx, coins, **kwargs)

def do_inspect_coin_cmd(ctx, coins, **kwargs):
    if kwargs.keys() == ['parent_id','puzzle_hash','amount']:
        coin_objs = [Coin(bytes.fromhex(kwargs['parent_id']), bytes.fromhex(kwargs['puzzle_hash']), uint64(amount))]
    else:
        coin_objs = []
        try:
            if type(coins[0]) == str:
                coin_objs = streamable_load(Coin, coins)
            else:
                coin_objs = coins
        except:
            print("One or more of the specified objects was not a coin")

    inspect_callback(coin_objs, ctx, id_calc=(lambda e: e.name()), type='Coin')