import click
import aiohttp
import asyncio
import json

from pprint import pprint

from chia.rpc.full_node_rpc_client import FullNodeRpcClient
from chia.util.default_root import DEFAULT_ROOT_PATH
from chia.util.config import load_config
from chia.util.ints import uint16
from chia.types.spend_bundle import SpendBundle
from chia.types.blockchain_format.coin import Coin

from cdv.cmds.chia_inspect import fake_context, do_inspect_spend_bundle_cmd

@click.group("rpc", short_help="Make RPC requests to a Chia full node")
def rpc_cmd():
    pass

async def get_client():
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        full_node_rpc_port = config["full_node"]["rpc_port"]
        full_node_client = await FullNodeRpcClient.create(self_hostname, uint16(full_node_rpc_port), DEFAULT_ROOT_PATH, config)
        return full_node_client
    except Exception as e:
        if isinstance(e, aiohttp.ClientConnectorError):
            pprint(f"Connection error. Check if full node is running at {full_node_rpc_port}")
        else:
            pprint(f"Exception from 'harvester' {e}")
        return None

@rpc_cmd.command("state", short_help="Gets the status of the blockchain (get_blockchain_state)")
def rpc_state_cmd():
    async def do_command():
        try:
            node_client = await get_client()
            state = await node_client.get_blockchain_state()
            state['peak'] = state['peak'].to_json_dict()
            pprint(state)
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("blocks", short_help="Gets blocks between two indexes (get_blocks)")
@click.option("-s","--start", required=True, help="The block index to start at (included)")
@click.option("-e","--end", required=True, help="The block index to end at (excluded)")
def rpc_blocks_cmd(start, end):
    async def do_command():
        try:
            node_client = await get_client()
            blocks = await node_client.get_all_block(start, end)
            pprint([block.to_json_dict() for block in blocks])
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("blockrecords", short_help="Gets block records between two indexes (get_block_records)")
@click.option("-s","--start", required=True, help="The block index to start at (included)")
@click.option("-e","--end", required=True, help="The block index to end at (excluded)")
def rpc_blockrecords_cmd(start, end):
    async def do_command():
        try:
            node_client = await get_client()
            block_records = await node_client.get_block_records(start, end)
            pprint(block_records)
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("blockcoins", short_help="Gets the coins added and removed for a specific header hash (get_additions_and_removals)")
@click.argument("headerhash", nargs=1, required=True)
def rpc_addrem_cmd(headerhash):
    async def do_command():
        try:
            node_client = await get_client()
            additions, removals = await node_client.get_additions_and_removals(bytes.fromhex(headerhash))
            additions = [rec.to_json_dict() for rec in additions]
            removals = [rec.to_json_dict() for rec in removals]
            pprint({'additions': additions, 'removals': removals})
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("blockspends", short_help="Gets the puzzle and solution for a coin spent at the specified block height (get_puzzle_and_solution)")
@click.option("-id","--coinid", required=True, help="The id of the coin that was spent")
@click.option("-h","--block-height", required=True, type=int, help="The block height in which the coin was spent")
def rpc_puzsol_cmd(coinid, block_height):
    async def do_command():
        try:
            node_client = await get_client()
            coin_spend = await node_client.get_puzzle_and_solution(bytes.fromhex(coinid), block_height)
            pprint(coin_spend)
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("pushtx", short_help="Pushes a spend bundle to the network (push_tx)")
@click.argument("spendbundles", nargs=-1, required=True)
def rpc_pushtx_cmd(spendbundles):
    async def do_command():
        try:
            node_client = await get_client()
            for bundle in do_inspect_spend_bundle_cmd(fake_context(), spendbundles, print_results=False):
                try:
                    result = await node_client.push_tx(bundle)
                    pprint(result)
                except ValueError as e:
                    pprint(str(e))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("coinrecords", short_help="Gets coin records by a specified information (get_coin_records_by_*)")
@click.argument("values", nargs=-1, required=True)
@click.option("--by", help="The property to use (id, puzzlehash, parentid)")
@click.option("-nd","--as-name-dict", is_flag=True, help="Return the records as a dictionary with ids as the keys")
@click.option("-ou","--only-unspent", is_flag=True, help="Exclude already spent coins from the search")
@click.option("-s","--start", type=int, help="The block index to start at (included)")
@click.option("-e","--end", type=int, help="The block index to end at (excluded)")
def rpc_coinrecords_cmd(values, by, as_name_dict, **kwargs):
    async def do_command(_kwargs):
        try:
            node_client = await get_client()
            clean_values = map(lambda value: value[2:] if value[:2] == "0x" else value, values)
            clean_values = [bytes.fromhex(value) for value in clean_values]
            if by in ["name","id"]:
                coin_records = [await node_client.get_coin_record_by_name(value) for value in clean_values]
                if not kwargs["include_spent_coins"]:
                    coin_records = list(filter(lambda record: record.spent == False, coin_records))
                if kwargs["start_height"] is not None:
                    coin_records = list(filter(lambda record: record.confirmed_block_index >= kwargs["start_height"], coin_records))
                if kwargs["end_height"] is not None:
                    coin_records = list(filter(lambda record: record.confirmed_block_index < kwargs["end_height"], coin_records))
            elif by in ["puzhash","puzzle_hash","puzzlehash"]:
                coin_records = await node_client.get_coin_records_by_puzzle_hashes(clean_values,**_kwargs)
            elif by in ["parent_id","parent_info","parent_coin_info","parentid","parentinfo","parent"]:
                coin_records = await node_client.get_coin_records_by_parent_ids(clean_values,**_kwargs)

            coin_records = [rec.to_json_dict() for rec in coin_records]

            if as_name_dict:
                cr_dict = {}
                for record in coin_records:
                    cr_dict[Coin.from_json_dict(record["coin"]).name().hex()] = record
                pprint(cr_dict)
            else:
                pprint(coin_records)
        finally:
            node_client.close()
            await node_client.await_closed()

    kwargs["include_spent_coins"] = not kwargs.pop("only_unspent")
    kwargs["start_height"] = kwargs.pop("start")
    kwargs["end_height"] = kwargs.pop("end")
    asyncio.get_event_loop().run_until_complete(do_command(kwargs))