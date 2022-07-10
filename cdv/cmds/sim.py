import asyncio
from typing import Optional

import click

from cdv.cmds.sim_utils import SIMULATOR_ROOT_PATH, execute_with_simulator, farm_blocks, set_auto_farm

"""
These functions are for the new Chia Simulator. This is currently a work in progress.
"""
all_groups = {
    "all": "chia_full_node_simulator chia_wallet".split(),
    "wallet": "chia_wallet",
    "simulator": "chia_full_node_simulator",
}


@click.group("sim", short_help="Configure and make requests to a Chia Simulator Full Node")
@click.option("--root-path", default=SIMULATOR_ROOT_PATH, help="Config file root", type=click.Path(), show_default=True)
@click.option(
    "-p",
    "--rpc-port",
    help=(
        "Set the port where the Simulator is hosting the RPC interface. "
        "See the rpc_port under full_node in config.yaml"
    ),
    type=int,
    default=None,
)
@click.pass_context
def sim_cmd(ctx: click.Context, root_path: str, rpc_port: Optional[int]) -> None:
    ctx.ensure_object(dict)
    ctx.obj["root_path"] = root_path
    ctx.obj["rpc_port"] = rpc_port


@sim_cmd.command("create", short_help="Guides you through the process of setting up a Chia Simulator")
@click.option("-f", "--fingerprint", type=int, required=False, help="Use your fingerprint to skip the key prompt")
@click.option("-p", "--plot-directory", type=str, required=False, help="Override Default simulation plot directory")
@click.option("-a", "--auto-farm", type=bool, required=False, help="Enable or Disable auto farming")
@click.pass_context
def create_simulator_config(
    ctx: click.Context, fingerprint: Optional[int], plot_directory: Optional[str], auto_farm: Optional[bool]
) -> None:
    pass


@sim_cmd.command("start", short_help="Start service groups")
@click.option("-r", "--restart", is_flag=True, type=bool, help="Restart running services")
@click.argument("group", type=click.Choice(list(all_groups.keys())), nargs=-1, required=True)
@click.pass_context
def start_cmd(ctx: click.Context, restart: bool, group: str) -> None:
    from chia.cmds.start_funcs import async_start

    asyncio.run(async_start(ctx.obj["root_path"], group, restart))


@sim_cmd.command("stop", short_help="Stop running services")
@click.option("-d", "--daemon", is_flag=True, type=bool, help="Stop daemon")
@click.argument("group", type=click.Choice(list(all_groups.keys())), nargs=-1, required=True)
@click.pass_context
def stop_cmd(ctx: click.Context, daemon: bool, group: str) -> None:
    import sys

    from chia.cmds.stop import async_stop

    sys.exit(asyncio.run(async_stop(ctx.obj["root_path"], group, daemon)))


@sim_cmd.command("status", short_help="Get information about the state of the simulator.")
@click.option("-f", "--fingerprint", type=int, required=False, help="Get detailed information on this fingerprint.")
@click.pass_context
def status_cmd(ctx: click.Context, fingerprint: Optional[int]) -> None:
    pass


@sim_cmd.command("revert", short_help="Reset chain to a previous block height.")
@click.option("-b", "--blocks", type=int, required=False, default=1, help="Number of blocks to delete.")
@click.option("-r", "--reset", is_flag=True, type=bool, help="Reset the chain to the genesis block")
@click.pass_context
def revert_cmd(ctx: click.Context, height: int, reset: bool) -> None:
    pass


@sim_cmd.command("farm", short_help="Farm blocks")
@click.option("-b", "--blocks", type=int, required=False, default=1, help="Amount of blocks to create")
@click.option("-tr", "--transaction", is_flag=True, type=bool, default=False, help="Only add transaction blocks")
@click.option("-ta", "--target-address", type=str, default="", help="Block reward address")
@click.pass_context
def farm_cmd(ctx: click.Context, blocks: int, transaction_only: bool, target_address: str) -> None:
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            farm_blocks,
            blocks,
            transaction_only,
            target_address,
        )
    )


@sim_cmd.command("autofarm", short_help="Enable or disable auto farming on transaction submission")
@click.option("-s", "--set_autofarm", type=bool, required=True, help="Enable or disable auto farming.")
@click.pass_context
def autofarm_cmd(ctx: click.Context, set_autofarm: Optional[bool]) -> None:
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            set_auto_farm,
            set_autofarm,
        )
    )
