from typing import List, Dict

from chia.util.hash import std_hash

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
            signatures.append(AugSchemeMPL.sign(sk, bytes(message, "utf-8")))
    return AugSchemeMPL.aggregate(signatures)


def aggregate_signatures(signatures: List[G2Element]) -> G2Element:
    return AugSchemeMPL.aggregate(signatures)
