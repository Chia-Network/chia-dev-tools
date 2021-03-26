"""
Pay to delegated puzzle or hidden puzzle

In this puzzle program, the solution must choose either a hidden puzzle or a
delegated puzzle on a given public key.

The given public key is morphed by adding an offset from the hash of the hidden puzzle
and itself, giving a new so-called "synthetic" public key which has the hidden puzzle
hidden inside of it.

If the hidden puzzle path is taken, the hidden puzzle and original public key will be revealed
which proves that it was hidden there in the first place.

This roughly corresponds to bitcoin's taproot.
"""
from typing import Union

from blspy import G1Element, PrivateKey
from clvm.casts import int_from_bytes

from lib.std.constants import GROUP_ORDER
from lib.std.util.hash import std_hash
from lib.std.util.load_clvm import load_clvm
from lib.std.types.program import Program
from lib.std.types.sized_bytes import bytes32
from lib.std.spends.defaults import DEFAULT_HIDDEN_PUZZLE, DEFAULT_HIDDEN_PUZZLE_HASH
from .p2_conditions import puzzle_for_conditions

MOD = load_clvm("./lib/std/clvm/p2_delegated_puzzle_or_hidden_puzzle.clvm")

SYNTHETIC_MOD = load_clvm("./lib/std/clvm/calculate_synthetic_public_key.clvm")

PublicKeyProgram = Union[bytes, Program]


def calculate_synthetic_offset(public_key: G1Element, hidden_puzzle_hash: bytes32) -> int:
    blob = std_hash(bytes(public_key) + hidden_puzzle_hash)
    offset = int_from_bytes(blob)
    offset %= GROUP_ORDER
    return offset


def calculate_synthetic_public_key(public_key: G1Element, hidden_puzzle_hash: bytes32) -> G1Element:
    r = SYNTHETIC_MOD.run([bytes(public_key), hidden_puzzle_hash])
    return G1Element.from_bytes(r.as_atom())


def calculate_synthetic_secret_key(secret_key: PrivateKey, hidden_puzzle_hash: bytes32) -> PrivateKey:
    secret_exponent = int.from_bytes(bytes(secret_key), "big")
    public_key = secret_key.get_g1()
    synthetic_offset = calculate_synthetic_offset(public_key, hidden_puzzle_hash)
    synthetic_secret_exponent = (secret_exponent + synthetic_offset) % GROUP_ORDER
    blob = synthetic_secret_exponent.to_bytes(32, "big")
    synthetic_secret_key = PrivateKey.from_bytes(blob)
    return synthetic_secret_key


def puzzle_for_synthetic_public_key(synthetic_public_key: G1Element) -> Program:
    return MOD.curry(bytes(synthetic_public_key))


def puzzle_for_public_key_and_hidden_puzzle_hash(public_key: G1Element, hidden_puzzle_hash: bytes32) -> Program:
    synthetic_public_key = calculate_synthetic_public_key(public_key, hidden_puzzle_hash)

    return puzzle_for_synthetic_public_key(synthetic_public_key)


def puzzle_for_public_key_and_hidden_puzzle(public_key: G1Element, hidden_puzzle: Program) -> Program:
    return puzzle_for_public_key_and_hidden_puzzle_hash(public_key, hidden_puzzle.get_tree_hash())


def puzzle_for_pk(public_key: G1Element) -> Program:
    return puzzle_for_public_key_and_hidden_puzzle_hash(public_key, DEFAULT_HIDDEN_PUZZLE_HASH)


def solution_for_delegated_puzzle(delegated_puzzle: Program, solution: Program) -> Program:
    return Program.to([[], delegated_puzzle, solution])


def solution_for_hidden_puzzle(
    hidden_public_key: G1Element,
    hidden_puzzle: Program,
    solution_to_hidden_puzzle: Program,
) -> Program:
    return Program.to([hidden_public_key, hidden_puzzle, solution_to_hidden_puzzle])


def solution_for_conditions(conditions) -> Program:
    delegated_puzzle = puzzle_for_conditions(conditions)
    return solution_for_delegated_puzzle(delegated_puzzle, Program.to(0))
