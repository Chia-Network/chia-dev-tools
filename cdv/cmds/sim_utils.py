import os
from pathlib import Path
from typing import Callable, Dict, Optional

from chia.consensus.coinbase import create_puzzlehash_for_pk
from chia.simulator.SimulatorFullNodeRpcClient import SimulatorFullNodeRpcClient
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.bech32m import encode_puzzle_hash, decode_puzzle_hash
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


def display_key_info(fingerprint: int) -> None:
    prefix = "txch"
    print(f"Using fingerprint {fingerprint}")
    private_key_and_seed = Keychain().get_private_key_by_fingerprint(fingerprint)
    if private_key_and_seed is None:
        print(f"Fingerprint {fingerprint} not found")
        return

    print(f"Showing all public and private keys for: {fingerprint}")
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
