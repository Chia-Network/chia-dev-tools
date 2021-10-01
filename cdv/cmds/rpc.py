import click
import aiohttp
import asyncio
import json

from typing import Dict, Optional, List, Tuple
from pprint import pprint

from chia.consensus.block_record import BlockRecord
from chia.rpc.full_node_rpc_client import FullNodeRpcClient
from chia.util.default_root import DEFAULT_ROOT_PATH
from chia.util.config import load_config
from chia.util.ints import uint16, uint64
from chia.util.misc import format_bytes
from chia.util.byte_types import hexstr_to_bytes
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_spend import CoinSpend
from chia.types.coin_record import CoinRecord
from chia.types.full_block import FullBlock
from chia.types.unfinished_header_block import UnfinishedHeaderBlock

from cdv.cmds.util import fake_context
from cdv.cmds.chia_inspect import do_inspect_spend_bundle_cmd


"""
These functions are untested because it is relatively basic code that would be very complex to test.
Please be careful when making changes.
"""


@click.group("rpc", short_help="Make RPC requests to a Chia full node")
def rpc_cmd():
    pass


# Loading the client requires the standard chia root directory configuration that all of the chia commands rely on
async def get_client() -> Optional[FullNodeRpcClient]:
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        full_node_rpc_port = config["full_node"]["rpc_port"]
        full_node_client = await FullNodeRpcClient.create(
            self_hostname, uint16(full_node_rpc_port), DEFAULT_ROOT_PATH, config
        )
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
            node_client: FullNodeRpcClient = await get_client()
            state: Dict = await node_client.get_blockchain_state()
            state["peak"] = state["peak"].to_json_dict()
            print(json.dumps(state, sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command("blocks", short_help="Gets blocks between two indexes (get_block(s))")
@click.option("-hh", "--header-hash", help="The header hash of the block to get")
@click.option("-s", "--start", help="The block index to start at (included)")
@click.option("-e", "--end", help="The block index to end at (excluded)")
def rpc_blocks_cmd(header_hash: str, start: int, end: int):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            if header_hash:
                blocks: List[FullBlock] = [await node_client.get_block(hexstr_to_bytes(header_hash))]
            elif start and end:
                blocks: List[FullBlock] = await node_client.get_all_block(start, end)
            else:
                print("Invalid arguments specified")
                return
            print(json.dumps([block.to_json_dict() for block in blocks], sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command(
    "blockrecords",
    short_help="Gets block records between two indexes (get_block_record(s), get_block_record_by_height)",
)
@click.option("-hh", "--header-hash", help="The header hash of the block to get")
@click.option("-i", "--height", help="The height of the block to get")  # This option is not in the standard RPC API
@click.option("-s", "--start", help="The block index to start at (included)")
@click.option("-e", "--end", help="The block index to end at (excluded)")
def rpc_blockrecords_cmd(header_hash: str, height: int, start: int, end: int):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            if header_hash:
                block_record: BlockRecord = await node_client.get_block_record(hexstr_to_bytes(header_hash))
                block_records: List = block_record.to_json_dict() if block_record else []
            elif height:
                block_record: BlockRecord = await node_client.get_block_record_by_height(height)
                block_records: List = block_record.to_json_dict() if block_record else []
            elif start and end:
                block_records: List = await node_client.get_block_records(start, end)
            else:
                print("Invalid arguments specified")
            print(json.dumps(block_records, sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


# This maybe shouldn't exist, I have yet to see it return anything but an empty list
@rpc_cmd.command(
    "unfinished",
    short_help="Returns the current unfinished header blocks (get_unfinished_block_headers)",
)
def rpc_unfinished_cmd():
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            header_blocks: List[UnfinishedHeaderBlock] = await node_client.get_unfinished_block_headers()
            print(json.dumps([block.to_json_dict() for block in header_blocks], sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


# Running this command plain should return the current total netspace estimation
@rpc_cmd.command(
    "space",
    short_help="Gets the netspace of the network between two blocks (get_network_space)",
)
@click.option("-old", "--older", help="The header hash of the older block")  # Default block 0
@click.option("-new", "--newer", help="The header hash of the newer block")  # Default block 0
@click.option("-s", "--start", help="The height of the block to start at")  # Default latest block
@click.option("-e", "--end", help="The height of the block to end at")  # Default latest block
def rpc_space_cmd(older: str, newer: str, start: int, end: int):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()

            if (older and start) or (newer and end):
                pprint("Invalid arguments specified.")
                return
            elif not any([older, start, newer, end]):
                pprint(format_bytes((await node_client.get_blockchain_state())["space"]))
                return
            else:
                if start:
                    start_hash: bytes32 = (await node_client.get_block_record_by_height(start)).header_hash
                elif older:
                    start_hash: bytes32 = hexstr_to_bytes(older)
                else:
                    start_hash: bytes32 = (await node_client.get_block_record_by_height(0)).header_hash

                if end:
                    end_hash: bytes32 = (await node_client.get_block_record_by_height(end)).header_hash
                elif newer:
                    end_hash: bytes32 = hexstr_to_bytes(newer)
                else:
                    end_hash: bytes32 = (
                        await node_client.get_block_record_by_height(
                            (await node_client.get_blockchain_state())["peak"].height
                        )
                    ).header_hash

            netspace: Optional[uint64] = await node_client.get_network_space(start_hash, end_hash)
            if netspace:
                pprint(format_bytes(netspace))
            else:
                pprint("Invalid block range specified")

        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command(
    "blockcoins",
    short_help="Gets the coins added and removed for a specific header hash (get_additions_and_removals)",
)
@click.argument("headerhash", nargs=1, required=True)
def rpc_addrem_cmd(headerhash: str):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            additions, removals = await node_client.get_additions_and_removals(hexstr_to_bytes(headerhash))
            additions: List[Dict] = [rec.to_json_dict() for rec in additions]
            removals: List[Dict] = [rec.to_json_dict() for rec in removals]
            print(json.dumps({"additions": additions, "removals": removals}, sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command(
    "blockspends",
    short_help="Gets the puzzle and solution for a coin spent at the specified block height (get_puzzle_and_solution)",
)
@click.option("-id", "--coinid", required=True, help="The id of the coin that was spent")
@click.option(
    "-h",
    "--block-height",
    required=True,
    type=int,
    help="The block height in which the coin was spent",
)
def rpc_puzsol_cmd(coinid: str, block_height: int):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            coin_spend: Optional[CoinSpend] = await node_client.get_puzzle_and_solution(
                bytes.fromhex(coinid), block_height
            )
            print(json.dumps(coin_spend.to_json_dict(), sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command("pushtx", short_help="Pushes a spend bundle to the network (push_tx)")
@click.argument("spendbundles", nargs=-1, required=True)
def rpc_pushtx_cmd(spendbundles: Tuple[str]):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            # It loads the spend bundle using cdv inspect
            for bundle in do_inspect_spend_bundle_cmd(fake_context(), spendbundles, print_results=False):
                try:
                    result: Dict = await node_client.push_tx(bundle)
                    print(json.dumps(result, sort_keys=True, indent=4))
                except ValueError as e:
                    pprint(str(e))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command(
    "mempool",
    short_help="Gets items that are currently sitting in the mempool (get_(all_)mempool_*)",
)
@click.option(
    "-txid",
    "--transaction-id",
    help="The ID of a spend bundle that is sitting in the mempool",
)
@click.option("--ids-only", is_flag=True, help="Only show the IDs of the retrieved spend bundles")
def rpc_mempool_cmd(transaction_id: str, ids_only: bool):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            if transaction_id:
                items = {}
                items[transaction_id] = await node_client.get_mempool_item_by_tx_id(hexstr_to_bytes(transaction_id))
            else:
                b_items: Dict = await node_client.get_all_mempool_items()
                items = {}
                for key in b_items.keys():
                    items[key.hex()] = b_items[key]

            if ids_only:
                print(json.dumps(list(items.keys()), sort_keys=True, indent=4))
            else:
                print(json.dumps(items, sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    asyncio.get_event_loop().run_until_complete(do_command())


@rpc_cmd.command(
    "coinrecords",
    short_help="Gets coin records by a specified information (get_coin_records_by_*)",
)
@click.argument("values", nargs=-1, required=True)
@click.option("--by", help="The property to use (id, puzzlehash, parentid)")
@click.option(
    "-nd",
    "--as-name-dict",
    is_flag=True,
    help="Return the records as a dictionary with ids as the keys",
)
@click.option(
    "-ou",
    "--only-unspent",
    is_flag=True,
    help="Exclude already spent coins from the search",
)
@click.option("-s", "--start", type=int, help="The block index to start at (included)")
@click.option("-e", "--end", type=int, help="The block index to end at (excluded)")
def rpc_coinrecords_cmd(values: Tuple[str], by: str, as_name_dict: bool, **kwargs):
    async def do_command():
        try:
            node_client: FullNodeRpcClient = await get_client()
            clean_values: bytes32 = map(lambda hex: hexstr_to_bytes(hex), values)
            if by in ["name", "id"]:
                # TODO: When a by-multiple-names rpc exits, use it instead
                coin_records: List[CoinRecord] = await node_client.get_coin_records_by_names(clean_values, **kwargs)
            elif by in ["puzhash", "puzzle_hash", "puzzlehash"]:
                coin_records: List[CoinRecord] = await node_client.get_coin_records_by_puzzle_hashes(
                    clean_values, **kwargs
                )
            elif by in [
                "parent_id",
                "parent_info",
                "parent_coin_info",
                "parentid",
                "parentinfo",
                "parent",
                "pid",
            ]:
                coin_records: List[CoinRecord] = await node_client.get_coin_records_by_parent_ids(
                    clean_values, **kwargs
                )
            else:
                print(f"Unaware of property {by}.")
                return

            coin_record_dicts: List[Dict] = [rec.to_json_dict() for rec in coin_records]

            if as_name_dict:
                cr_dict = {}
                for record in coin_record_dicts:
                    cr_dict[Coin.from_json_dict(record["coin"]).name().hex()] = record
                print(json.dumps(cr_dict, sort_keys=True, indent=4))
            else:
                print(json.dumps(coin_record_dicts, sort_keys=True, indent=4))
        finally:
            node_client.close()
            await node_client.await_closed()

    # Have to rename the kwargs as they will be directly passed to the RPC client
    kwargs["include_spent_coins"] = not kwargs.pop("only_unspent")
    kwargs["start_height"] = kwargs.pop("start")
    kwargs["end_height"] = kwargs.pop("end")
    asyncio.get_event_loop().run_until_complete(do_command())
