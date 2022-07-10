import os
from pathlib import Path
from typing import Callable, Dict, Optional

from chia.simulator.SimulatorFullNodeRpcClient import SimulatorFullNodeRpcClient
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.byte_types import hexstr_to_bytes

SIMULATOR_ROOT_PATH = Path(os.path.expanduser(os.getenv("CHIA_SIMULATOR_ROOT", "~/.chia/simulator"))).resolve()


# based on execute_with_node
async def execute_with_simulator(rpc_port: Optional[int], root_path: Path, function: Callable, *args) -> None:
    import traceback

    from aiohttp import ClientConnectorError
    from chia.util.config import load_config
    from chia.util.ints import uint16

    config = load_config(root_path, "config.yaml")
    self_hostname = config["self_hostname"]
    if rpc_port is None:
        rpc_port = config["full_node"]["rpc_port"]
    try:
        node_client: SimulatorFullNodeRpcClient = await SimulatorFullNodeRpcClient.create(
            self_hostname, uint16(rpc_port), root_path, config
        )
        await function(node_client, config, *args)

    except Exception as e:
        if isinstance(e, ClientConnectorError):
            print(f"Connection error. Check if simulator rpc is running at {rpc_port}")
            print("This is normal if full node is still starting up")
        else:
            tb = traceback.format_exc()
            print(f"Exception from 'sim' {tb}")

    node_client.close()
    await node_client.await_closed()


async def farm_blocks(
    node_client: SimulatorFullNodeRpcClient,
    config: Dict,
    num_blocks: int,
    transaction_blocks: bool,
    target_address: str,
) -> None:
    if target_address == "":
        target_address = config["simulator"]["target_address"]
        if target_address is None:
            print("No target address in config, either rerun 'cdv sim create' or use --target-address to specify one")
            return
    target_ph = bytes32(hexstr_to_bytes(target_address))
    await node_client.farm_block(target_ph, num_blocks, transaction_blocks)
    print(f"Farmed {num_blocks}{' Transaction' if transaction_blocks else ''} blocks")
    block_height = (await node_client.get_blockchain_state())["peak"].height
    print(f"Block Height is now: {block_height}")


async def set_auto_farm(node_client: SimulatorFullNodeRpcClient, _config: Dict, set_autofarm: bool) -> None:
    current = await node_client.get_auto_farming()
    if current == set_autofarm:
        print(f"Auto farming is already {'enabled' if set_autofarm else 'disabled'}")
        return
    result = await node_client.set_auto_farming(set_autofarm)
    print(f"Auto farming is now {'enabled' if result else 'disabled'}")
