import os
from pathlib import Path
from typing import Callable, Optional

from chia.simulator.SimulatorFullNodeRpcClient import SimulatorFullNodeRpcClient

SIMULATOR_ROOT_PATH = Path(os.path.expanduser(os.getenv("CHIA_SIMULATOR_ROOT", "~/.chia/simulator"))).resolve()


# based on execute_with_node
async def execute_with_simulator(
    rpc_port: Optional[int], function: Callable, root_path: Path = SIMULATOR_ROOT_PATH, *args
) -> None:
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
