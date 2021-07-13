from typing import List, Dict

from chia.util.hash import std_hash
from chia.util.ints import uint32
from chia.wallet.derive_keys import (
    _derive_path,
    master_sk_to_farmer_sk,
    master_sk_to_pool_sk,
    master_sk_to_wallet_sk,
    master_sk_to_local_sk,
    master_sk_to_backup_sk,
)

from blspy import BasicSchemeMPL, PrivateKey, G1Element, AugSchemeMPL, G2Element

def secret_exponent_for_index(index: int) -> int:
    blob = index.to_bytes(32, "big")
    hashed_blob = BasicSchemeMPL.key_gen(std_hash(b"foo" + blob))
    r = int.from_bytes(hashed_blob, "big")
    return r


def private_key_for_index(index: int) -> PrivateKey:
    r = secret_exponent_for_index(index)
    return PrivateKey.from_bytes(r.to_bytes(32, "big"))


def public_key_for_index(index: int) -> G1Element:
    return private_key_for_index(index).get_g1()


def sign_message_with_index(index: int, message: str) -> G2Element:
    sk = private_key_for_index(index)
    return AugSchemeMPL.sign(sk, bytes(message, "utf-8"))


def sign_messages_with_indexes(sign_ops: List[Dict[int, str]]) -> G2Element:
    signatures = []
    for _ in sign_ops:
        for index, message in _.items():
            sk = private_key_for_index(index)
            signatures.append(AugSchemeMPL.sign(sk,bytes(message, "utf-8")))
    return AugSchemeMPL.aggregate(signatures)


def aggregate_signatures(signatures: List[G2Element]) -> G2Element:
    return AugSchemeMPL.aggregate(signatures)


# EIP 2334 bls key derivation
# https://eips.ethereum.org/EIPS/eip-2334
# 12381 = bls spec number
# 8444 = Chia blockchain number and port number
# 0, 1, 2, 3, 4, farmer, pool, wallet, local, backup key numbers


def _derive_path(sk: PrivateKey, path: List[int]) -> PrivateKey:
    for index in path:
        sk = AugSchemeMPL.derive_child_sk(sk, index)
    return sk


def master_sk_to_farmer_sk(master: PrivateKey) -> PrivateKey:
    return _derive_path(master, [12381, 8444, 0, 0])


def master_sk_to_pool_sk(master: PrivateKey) -> PrivateKey:
    return _derive_path(master, [12381, 8444, 1, 0])


def master_sk_to_wallet_sk(master: PrivateKey, index: uint32) -> PrivateKey:
    return _derive_path(master, [12381, 8444, 2, index])


def master_sk_to_local_sk(master: PrivateKey) -> PrivateKey:
    return _derive_path(master, [12381, 8444, 3, 0])


def master_sk_to_backup_sk(master: PrivateKey) -> PrivateKey:
    return _derive_path(master, [12381, 8444, 4, 0])
