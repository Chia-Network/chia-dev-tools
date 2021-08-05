import click
import aiohttp
import asyncio
import json

from pprint import pprint

from chia.rpc.full_node_rpc_client import FullNodeRpcClient
from chia.util.default_root import DEFAULT_ROOT_PATH
from chia.util.config import load_config
from chia.util.ints import uint16
from chia.util.misc import format_bytes
from chia.util.byte_types import hexstr_to_bytes
from chia.types.spend_bundle import SpendBundle
from chia.types.blockchain_format.coin import Coin

from cdv.cmds.util import fake_context
from cdv.cmds.chia_inspect import do_inspect_spend_bundle_cmd

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

@rpc_cmd.command("blocks", short_help="Gets blocks between two indexes (get_block(s))")
@click.option("-hh","--header-hash", help="The header hash of the block to get")
@click.option("-s","--start", help="The block index to start at (included)")
@click.option("-e","--end", help="The block index to end at (excluded)")
def rpc_blocks_cmd(header_hash, start, end):
    async def do_command():
        try:
            node_client = await get_client()
            if header_hash:
                blocks = [await node_client.get_block(hexstr_to_bytes(header_hash))]
            elif start and end:
                blocks = await node_client.get_all_block(start, end)
            else:
                print("Invalid arguments specified")
                return
            pprint([block.to_json_dict() for block in blocks])
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("blockrecords", short_help="Gets block records between two indexes (get_block_record(s), get_block_record_by_height)")
@click.option("-hh","--header-hash", help="The header hash of the block to get")
@click.option("-i","--height", help="The height of the block to get")
@click.option("-s","--start", help="The block index to start at (included)")
@click.option("-e","--end", help="The block index to end at (excluded)")
def rpc_blockrecords_cmd(header_hash, height, start, end):
    async def do_command():
        try:
            node_client = await get_client()
            if header_hash:
                block_record = await node_client.get_block_record(hexstr_to_bytes(header_hash))
                block_records = block_record.to_json_dict() if block_record else []
            elif height:
                block_record = await node_client.get_block_record_by_height(height)
                block_records = block_record.to_json_dict() if block_record else []
            elif start and end:
                block_records = await node_client.get_block_records(start, end)
            else:
                print("Invalid arguments specified")
            pprint(block_records)
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("unfinished", short_help="Returns the current unfinished header blocks (get_unfinished_block_headers)")
def rpc_unfinished_cmd():
    async def do_command():
        try:
            node_client = await get_client()
            header_blocks = await node_client.get_unfinished_block_headers()
            pprint([block.to_json_dict() for block in header_blocks])
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())

@rpc_cmd.command("space", short_help="Gets the netspace of the network between two blocks (get_network_space)")
@click.option("-old","--older", help="The header hash of the older block")
@click.option("-new","--newer", help="The header hash of the newer block")
@click.option("-s","--start", help="The height of the block to start at")
@click.option("-e","--end", help="The height of the block to end at")
def rpc_space_cmd(older, newer, start, end):
    async def do_command():
        try:
            node_client = await get_client()

            if (older and start) or (newer and end):
                pprint("Invalid arguments specified.")
            else:
                if start:
                    start_hash = (await node_client.get_block_record_by_height(start)).header_hash
                elif older:
                    start_hash = hexstr_to_bytes(older)
                else:
                    start_hash = (await node_client.get_block_record_by_height(0)).header_hash

                if end:
                    end_hash = (await node_client.get_block_record_by_height(end)).header_hash
                elif newer:
                    end_hash = hexstr_to_bytes(newer)
                else:
                    end_hash = (await node_client.get_block_record_by_height((await node_client.get_blockchain_state())["peak"].height)).header_hash

            netspace = await node_client.get_network_space(start_hash, end_hash)
            if netspace:
                pprint(format_bytes(netspace))
            else:
                pprint("Invalid block range specified")

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

@rpc_cmd.command("mempool", short_help="Gets items that are currently sitting in the mempool (get_(all_)mempool_*)")
@click.option("-txid","--transaction-id", help="The ID of a spend bundle that is sitting in the mempool")
@click.option("--ids-only", is_flag=True, help="Only show the IDs of the retrieved spend bundles")
def rpc_mempool_cmd(transaction_id, ids_only):
    async def do_command():
        try:
            node_client = await get_client()
            if transaction_id:
                items = {}
                items[transaction_id] = await node_client.get_mempool_item_by_tx_id(hexstr_to_bytes(transaction_id))
            else:
                b_items = await node_client.get_all_mempool_items()
                items = {}
                for key in b_items.keys():
                    items[key.hex()] = b_items[key]

            if ids_only:
                pprint(list(items.keys()))
            else:
                pprint(items)
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