import os
from decimal import Decimal
from pathlib import Path
from random import randint
from typing import Any, Callable, Dict, List, Optional

from blspy import PrivateKey
from chia.consensus.coinbase import create_puzzlehash_for_pk
from chia.simulator.simulator_full_node_rpc_client import SimulatorFullNodeRpcClient
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_record import CoinRecord
from chia.util.bech32m import decode_puzzle_hash, encode_puzzle_hash
from chia.util.config import load_config, save_config
from chia.util.ints import uint32
from chia.util.keychain import Keychain, bytes_to_mnemonic
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


async def start_async(root_path: Path, group: Any, restart: bool) -> None:
    import sys

    from chia.cmds.start_funcs import async_start

    sys.argv[0] = sys.argv[0].replace("cdv", "chia")  # this is the best way I swear.
    if root_path.exists():
        config = load_config(root_path, "config.yaml")
        await async_start(root_path, config, group, restart)
    else:
        print(f"Simulator root path: {root_path} does not exist.")
        print("please run 'cdv sim create' to create and configure a new simulator.")


def get_ph_from_fingerprint(fingerprint: int, key_id: int = 1) -> bytes32:
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

    if not chia_root.is_dir() or not Path(chia_root / "config" / "config.yaml").exists():
        # create chia directories
        chia_init(chia_root, testnet=True)
        # modify config file to put it on its own testnet.
        config = load_config(chia_root, "config.yaml")
        config["full_node"]["send_uncompact_interval"] = 0
        config["full_node"]["target_uncompact_proofs"] = 30
        config["full_node"]["peer_connect_interval"] = 50
        config["full_node"]["sanitize_weight_proof_only"] = False
        config["network_overrides"]["constants"]["simulator0"] = config["network_overrides"]["constants"][
            "testnet0"
        ].copy()
        config["network_overrides"]["config"]["simulator0"] = config["network_overrides"]["config"]["testnet0"].copy()
        # config["logging"]["log_stdout"] = True  # Not sure if we want this.
        # make sure we don't try to connect to other nodes.
        config["full_node"]["introducer_peer"] = None
        config["wallet"]["introducer_peer"] = None
        config["full_node"]["dns_servers"] = []
        config["wallet"]["dns_servers"] = []
        # set ports and networks, we mostly just add 4 to the port.
        # this is dependent on the length of the name of the simulator * a random number which should be good.
        port_offset = len(chia_root.parts[-1]) * randint(1, 20)
        config["selected_network"] = "simulator0"
        config["daemon_port"] = config["daemon_port"] + port_offset
        config["network_overrides"]["config"]["simulator0"]["default_full_node_port"] = 38444 + port_offset
        for service in ["harvester", "farmer", "full_node", "wallet", "introducer", "timelord", "pool", "ui"]:
            config[service]["selected_network"] = "simulator0"
            if config[service].get("rpc_port") is not None and config[service].get("port") is not None:
                config[service]["port"] = port_offset + config[service]["port"]
                config[service]["rpc_port"] = port_offset + config[service]["rpc_port"]
    else:
        config = load_config(chia_root, "config.yaml")
    # simulator overrides
    config["simulator"]["key_fingerprint"] = fingerprint
    if farming_address is None:
        farming_address = encode_puzzle_hash(get_ph_from_fingerprint(fingerprint), "txch")
    config["simulator"]["farming_address"] = farming_address
    if plot_directory is not None:
        config["simulator"]["plot_directory"] = plot_directory
    config["simulator"]["auto_farm"] = auto_farm if auto_farm is not None else True
    # change genesis block to give the user the reward
    farming_ph = decode_puzzle_hash(farming_address)
    # modify testnet0 consts to give the user the reward
    simulator_consts = config["network_overrides"]["constants"]["simulator0"]
    simulator_consts["GENESIS_PRE_FARM_FARMER_PUZZLE_HASH"] = farming_ph.hex()
    simulator_consts["GENESIS_PRE_FARM_POOL_PUZZLE_HASH"] = farming_ph.hex()
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
    sk, seed = private_key_and_seed
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


def generate_and_return_fingerprint() -> int:
    """
    Generate and add new PrivateKey and return its fingerprint.
    """
    from chia.util.keychain import generate_mnemonic

    print("Generating private key")
    sk = Keychain().add_private_key(generate_mnemonic(), "")
    fingerprint: int = sk.get_g1().get_fingerprint()
    print(f"Added private key with public key fingerprint {fingerprint}")
    return fingerprint


def select_fingerprint(fingerprint: Optional[int] = None) -> Optional[int]:
    """
    Either select an existing fingerprint or create one and return it.
    """
    fingerprints = [pk.get_fingerprint() for pk in Keychain().get_all_public_keys()]
    if fingerprint is not None and fingerprint in fingerprints:
        return fingerprint
    elif fingerprint is not None and fingerprint not in fingerprints:
        print(f"Invalid Fingerprint. Fingerprint {fingerprint} was not found.")
        return None
    if len(fingerprints) == 0:
        if (
            input("No keys in keychain. Press 'q' to quit, or press any other key to generate a new key.").lower()
            == "q"
        ):
            return None
        else:
            # generate private key and add to wallet
            fingerprint = generate_and_return_fingerprint()
    else:
        print("Fingerprints:")
        print(
            "If you already used one of these keys, select that fingerprint to skip the plotting process."
            " Otherwise, select any key below."
        )
        for i, fp in enumerate(fingerprints):
            row: str = f"{i + 1}) "
            row += f"{fp}"
            print(row)
        val = None
        prompt: str = f"Choose a simulator key [1-{len(fingerprints)}] ('q' to quit, or 'g' to generate a new key): "
        while val is None:
            val = input(prompt)
            if val == "q":
                return None
            elif val == "g":
                fingerprint = generate_and_return_fingerprint()
                break
            elif not val.isdigit():
                val = None
            else:
                index = int(val) - 1
                if index < 0 or index >= len(fingerprints):
                    print("Invalid value")
                    val = None
                    continue
                else:
                    fingerprint = fingerprints[index]
        assert fingerprint is not None
    return fingerprint


async def generate_plots(config: Dict[str, Any], root_path: Path, fingerprint: int) -> None:
    """
    Pre-Generate plots for the new simulator instance.
    """
    from time import time

    from chia.simulator.block_tools import BlockTools, test_constants
    from chia.simulator.start_simulator import PLOT_SIZE, PLOTS

    farming_puzzle_hash = decode_puzzle_hash(config["simulator"]["farming_address"])

    # create block tools and use local keychain
    bt = BlockTools(
        test_constants,
        root_path,
        automated_testing=False,
        plot_dir=config["simulator"].get("plot_directory", "plots"),
        keychain=Keychain(),
    )
    await bt.setup_keys(fingerprint=fingerprint, reward_ph=farming_puzzle_hash)
    starting_time = time()
    await bt.setup_plots(num_og_plots=PLOTS, num_pool_plots=0, num_non_keychain_plots=0, plot_size=PLOT_SIZE)
    print(f"{'New plots generated.' if time() - starting_time > 5 else 'Using Existing Plots'}\n")


async def async_config_wizard(
    root_path: Path,
    fingerprint: Optional[int],
    farming_address: Optional[str],
    plot_directory: Optional[str],
    auto_farm: Optional[bool],
) -> None:
    # either return passed through fingerprint or get one
    fingerprint = select_fingerprint(fingerprint)
    if fingerprint is None:
        # user cancelled wizard
        return
    # create chia directory & get config.
    print("Creating chia directory & config...")
    config = create_chia_directory(root_path, fingerprint, farming_address, plot_directory, auto_farm)
    print(f"\nFarming & Prefarm reward address: {config['simulator']['farming_address']}")
    # Pre-generate plots by running block_tools init functions.
    print("Please Wait, Generating plots...")
    print("This may take up to a minute if you are on a slow machine")

    await generate_plots(config, root_path, fingerprint)
    # final messages
    print("Configuration Wizard Complete.")
    print("Starting Simulator now...\n\n")
    await start_async(root_path, ("simulator",), False)


def print_coin_record(
    name: str,
    address_prefix: str,
    mojo_per_unit: int,
    coin_record: CoinRecord,
) -> None:
    from datetime import datetime

    chia_amount = Decimal(int(coin_record.coin.amount)) / mojo_per_unit
    coin_address = encode_puzzle_hash(coin_record.coin.puzzle_hash, address_prefix)
    print(f"Coin 0x{coin_record.name.hex()}")
    print(f"Wallet Address: {coin_address}")
    print(f"Confirmed at block: {coin_record.confirmed_block_index}")
    print(f"Spent: {f'at Block {coin_record.spent_block_index}' if coin_record.spent else 'No'}")
    print(f"Coin Amount: {chia_amount} {name}")
    print(f"Parent Coin ID: 0x{coin_record.coin.parent_coin_info.hex()}")
    print(f"Created at: {datetime.fromtimestamp(float(coin_record.timestamp)).strftime('%Y-%m-%d %H:%M:%S')}\n")


async def print_coin_records(
    config: Dict[str, Any],
    node_client: SimulatorFullNodeRpcClient,
    include_reward_coins: bool,
    include_spent: bool = False,
) -> None:
    import sys

    from chia.cmds.units import units

    coin_records: List[CoinRecord] = await node_client.get_all_coins(include_spent)
    coin_records = [coin_record for coin_record in coin_records if not coin_record.coinbase or include_reward_coins]
    paginate = False  # I might change this later.
    if len(coin_records) != 0:
        print("All Coins: ")
        if paginate is True:
            paginate = sys.stdout.isatty()
        address_prefix = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"]
        name = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"].upper()
        mojo_per_unit = units["chia"]
        num_per_screen = 5 if paginate else len(coin_records)
        # ripped from cmds/wallet_funcs.
        for i in range(0, len(coin_records), num_per_screen):
            for j in range(0, num_per_screen):
                if i + j >= len(coin_records):
                    break
                print_coin_record(
                    coin_record=coin_records[i + j],
                    name=name,
                    address_prefix=address_prefix,
                    mojo_per_unit=mojo_per_unit,
                )
            if i + num_per_screen <= len(coin_records) and paginate:
                print("Press q to quit, or c to continue")
                while True:
                    entered_key = sys.stdin.read(1)
                    if entered_key == "q":
                        return None
                    elif entered_key == "c":
                        break


async def print_wallets(config: Dict[str, Any], node_client: SimulatorFullNodeRpcClient) -> None:
    from chia.cmds.units import units

    ph_and_amount = await node_client.get_all_puzzle_hashes()
    address_prefix = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"]
    name = config["network_overrides"]["config"][config["selected_network"]]["address_prefix"].upper()
    mojo_per_unit = units["chia"]
    for puzzle_hash, (amount, num_tx) in ph_and_amount.items():
        address = encode_puzzle_hash(puzzle_hash, address_prefix)
        chia_amount = Decimal(int(amount)) / mojo_per_unit
        print(f"Address: {address} Has a balance of: {chia_amount} {name}, with a total of: {num_tx}, transactions.\n")


async def print_status(
    node_client: SimulatorFullNodeRpcClient,
    config: Dict,
    fingerprint: Optional[int],
    show_key: bool,
    show_coins: bool,
    include_reward_coins: bool,
    show_addresses: bool,
) -> None:
    from chia.cmds.show import print_blockchain_state  # TODO: JACK FIX THIS
    from chia.cmds.units import units

    # Display keychain info
    if show_key:
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
        f"with a balance of: "
        f"{sum(coin_records.coin.amount for coin_records in farming_coin_records) / units['chia']} TXCH."
    )
    if show_addresses:
        print("All Addresses: ")
        await print_wallets(config, node_client)
    if show_coins:
        await print_coin_records(config, node_client, include_reward_coins)


async def revert_block_height(
    node_client: SimulatorFullNodeRpcClient,
    _: Dict,
    num_blocks: int,
    num_new_blocks: int,
    reset_chain_to_genesis: bool,
    use_revert_blocks: bool,
) -> None:
    if use_revert_blocks:
        if num_new_blocks != 1:
            print(f"Ignoring num_new_blocks: {num_new_blocks}, because we are not performing a reorg.")
        # in this case num_blocks is the number of blocks to delete
        new_height: int = await node_client.revert_blocks(num_blocks, reset_chain_to_genesis)
        print(
            f"All transactions in Block: {new_height + num_blocks} and above were successfully deleted, "
            "you should now delete & restart all wallets."
        )
    else:
        # However, in this case num_blocks is the fork height.
        new_height = await node_client.reorg_blocks(num_blocks, num_new_blocks, use_revert_blocks)
        old_height = new_height - num_new_blocks
        print(f"All transactions in Block: {old_height - num_blocks} and above were successfully reverted.")
    print(f"Block Height is now: {new_height}")


async def farm_blocks(
    node_client: SimulatorFullNodeRpcClient,
    config: Dict,
    num_blocks: int,
    transaction_blocks: bool,
    target_address: str,
) -> None:
    if target_address == "":
        target_address = config["simulator"]["farming_address"]
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
        print(f"Auto farming is already {'on' if set_autofarm else 'off'}")
        return
    result = await node_client.set_auto_farming(set_autofarm)
    print(f"Auto farming is now {'on' if result else 'off'}")
