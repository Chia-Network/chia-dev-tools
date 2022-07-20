import os
from pathlib import Path
from typing import Callable, Dict, Optional, Any

from chia.consensus.coinbase import create_puzzlehash_for_pk
from chia.simulator.SimulatorFullNodeRpcClient import SimulatorFullNodeRpcClient
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.bech32m import encode_puzzle_hash, decode_puzzle_hash
from chia.util.config import save_config, load_config
from chia.util.ints import uint32
from blspy import PrivateKey
from chia.util.keychain import Keychain
from chia.util.keychain import bytes_to_mnemonic
from chia.wallet.derive_keys import (
    master_sk_to_farmer_sk,
    master_sk_to_pool_sk,
    master_sk_to_wallet_sk,
    master_sk_to_wallet_sk_unhardened,
)

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


def get_puzzle_hash_from_key(fingerprint: int, key_id: int = 1) -> bytes32:
    priv_key_and_entropy = Keychain().get_private_key_by_fingerprint(fingerprint)
    if priv_key_and_entropy is None:
        raise Exception("Fingerprint not found")
    private_key = priv_key_and_entropy[0]
    sk_for_wallet_id: PrivateKey = master_sk_to_wallet_sk(private_key, uint32(key_id))
    puzzle_hash: bytes32 = create_puzzlehash_for_pk(sk_for_wallet_id.get_g1())
    return puzzle_hash


def create_chia_directory(
    chia_root: Path,
    fingerprint: int,
    farming_address: Optional[str],
    plot_directory: Optional[str],
    auto_farm: Optional[bool],
) -> Dict[str, Any]:
    from chia.cmds.init_funcs import chia_init

    # create chia directories
    chia_init(chia_root, testnet=True)
    # modify config file to put it on its own testnet.
    config = load_config(chia_root, "config.yaml")
    config["full_node"]["send_uncompact_interval"] = 0
    config["full_node"]["target_uncompact_proofs"] = 30
    config["full_node"]["peer_connect_interval"] = 50
    config["full_node"]["sanitize_weight_proof_only"] = False
    config["logging"]["log_stdout"] = True
    config["selected_network"] = "testnet0"
    # make sure we don't try to connect to other nodes.
    config["full_node"]["introducer_peer"] = None
    config["wallet"]["introducer_peer"] = None
    config["full_node"]["dns_servers"] = []
    config["wallet"]["dns_servers"] = []
    for service in ["harvester", "farmer", "full_node", "wallet", "introducer", "timelord", "pool", "simulator", "ui"]:
        config[service]["selected_network"] = "testnet0"
    # simulator overrides
    config["simulator"]["key_fingerprint"] = fingerprint
    if farming_address is None:
        farming_address = encode_puzzle_hash(get_puzzle_hash_from_key(fingerprint), "txch")
    config["simulator"]["farming_address"] = farming_address
    if plot_directory is not None:
        config["simulator"]["plot_directory"] = plot_directory
    if auto_farm is not None:
        config["simulator"]["auto_farm"] = auto_farm
    # change genesis block to give the user the reward
    farming_ph = decode_puzzle_hash(farming_address)
    testnet0_consts = config["network_overrides"]["constants"]["testnet0"]
    testnet0_consts["GENESIS_PRE_FARM_FARMER_PUZZLE_HASH"] = farming_ph
    testnet0_consts["GENESIS_PRE_FARM_POOL_PUZZLE_HASH"] = farming_ph
    # save config and return the config
    save_config(chia_root, "config.yaml", config)
    return config


def display_key_info(fingerprint: int) -> None:
    prefix = "txch"
    print(f"Using fingerprint {fingerprint}")
    private_key_and_seed = Keychain().get_private_key_by_fingerprint(fingerprint)
    if private_key_and_seed is None:
        print(f"Fingerprint {fingerprint} not found")
        return

    for sk, seed in private_key_and_seed:
        print("\nFingerprint:", sk.get_g1().get_fingerprint())
        print("Master public key (m):", sk.get_g1())
        print("Farmer public key (m/12381/8444/0/0):", master_sk_to_farmer_sk(sk).get_g1())
        print("Pool public key (m/12381/8444/1/0):", master_sk_to_pool_sk(sk).get_g1())
        first_wallet_sk: PrivateKey = master_sk_to_wallet_sk_unhardened(sk, uint32(0))
        wallet_address: str = encode_puzzle_hash(create_puzzlehash_for_pk(first_wallet_sk.get_g1()), prefix)
        print(f"First wallet address: {wallet_address}")
        assert seed is not None
        print("Master private key (m):", bytes(sk).hex())
        print("First wallet secret key (m/12381/8444/2/0):", master_sk_to_wallet_sk(sk, uint32(0)))
        mnemonic = bytes_to_mnemonic(seed)
        print("  Mnemonic seed (24 secret words):")
        print(f"{mnemonic} \n")


async def generate_plots(root_path: Path) -> None:
    import sys
    from chia.simulator.start_simulator import main as start_simulator

    # temporarily clear sys.argv to avoid issues with config.yaml
    sys_argv = sys.argv.copy()
    sys.argv = [sys.argv[0]]
    # because we run this function in test mode, it creates block tools,
    # and it returns a service which we don't care about.
    await start_simulator(True, root_path)
    sys.argv = sys_argv  # restore sys.argv


async def async_config_wizard(
    root_path: Path,
    fingerprint: Optional[int],
    farming_address: Optional[str],
    plot_directory: Optional[str],
    auto_farm: Optional[bool],
) -> None:
    if fingerprint is None:
        return
    # create chia directory & get config.
    config = create_chia_directory(root_path, fingerprint, farming_address, plot_directory, auto_farm)
    print(f"Farming & Prefarm reward address: {config['simulator']['farming_address']}")
    # Pre-generate plots by running block_tools init functions.
    print("Please Wait, Generating plots...\n")
    print("This may take up to a minute if on a slow machine.\n")
    await generate_plots(root_path)
    print("\nPlots generated.\n")
    # final messages
    print("Configuration Wizard Complete.")
    print("\nPlease run 'chia start simulator' to start the simulator.")


async def print_status(
    node_client: SimulatorFullNodeRpcClient,
    config: Dict,
    fingerprint: Optional[int],
    show_coins: bool,
    show_puzzles: bool,
) -> None:
    from chia.cmds.show import print_blockchain_state

    # Display keychain info
    if fingerprint is None:
        fingerprint = config["simulator"]["key_fingerprint"]
    if fingerprint is not None:
        display_key_info(fingerprint)
    else:
        print(
            "No fingerprint in config, either rerun 'cdv sim create' "
            "or use --fingerprint to specify one, skipping key information."
        )
    # chain status ( basically chia show -s)
    await print_blockchain_state(node_client, config)
    print("")
    # farming information
    target_ph: bytes32 = await node_client.get_farming_ph()
    farming_coin_records = await node_client.get_coin_records_by_puzzle_hash(target_ph, False)
    print(
        f"Current Farming address: {encode_puzzle_hash(target_ph, 'txch')}, "
        f"with a balance of: {sum(coin_records.coin.amount for coin_records in farming_coin_records)} TXCH."
    )
    if show_puzzles:
        ...
        # TODO: get balances of all addresses with a balance on the chain (Probably needs new rpc call)
    if show_coins:
        ...
        # TODO: Show all non spent coins (Need new RPC)


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
        print(
            "No target address in config, falling back to the temporary address currently in use. "
            "You can use 'cdv sim create' or use --target-address to specify a different address."
        )
        target_ph: bytes32 = await node_client.get_farming_ph()
    else:
        target_ph = decode_puzzle_hash(target_address)
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
