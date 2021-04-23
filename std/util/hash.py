import blspy
from typing import Optional, Set

from clvm import CLVMObject

from lib.std.types.sized_bytes import bytes32


def std_hash(b) -> bytes32:
    """
    The standard hash used in many places.
    """
    return bytes32(blspy.Util.hash256(bytes(b)))

def std_literal_tree_hash(literal) -> bytes32:
    return std_hash((bytes.fromhex("01") + literal))


"""
This is an implementation of `sha256_treehash`, used to calculate
puzzle hashes in clvm.

This implementation goes to great pains to be non-recursive so we don't
have to worry about blowing out the python stack.
"""
def std_treehash(sexp: CLVMObject, precalculated: Optional[Set[bytes32]] = None) -> bytes32:
    """
    Hash values in `precalculated` are presumed to have been hashed already.
    """

    if precalculated is None:
        precalculated = set()

    def handle_sexp(sexp_stack, op_stack, precalculated: Set[bytes32]) -> None:
        sexp = sexp_stack.pop()
        if sexp.pair:
            p0, p1 = sexp.pair
            sexp_stack.append(p0)
            sexp_stack.append(p1)
            op_stack.append(handle_pair)
            op_stack.append(handle_sexp)
            op_stack.append(roll)
            op_stack.append(handle_sexp)
        else:
            if sexp.atom in precalculated:
                r = sexp.atom
            else:
                r = std_hash(b"\1" + sexp.atom)
            sexp_stack.append(r)

    def handle_pair(sexp_stack, op_stack, precalculated) -> None:
        p0 = sexp_stack.pop()
        p1 = sexp_stack.pop()
        sexp_stack.append(std_hash(b"\2" + p0 + p1))

    def roll(sexp_stack, op_stack, precalculated) -> None:
        p0 = sexp_stack.pop()
        p1 = sexp_stack.pop()
        sexp_stack.append(p0)
        sexp_stack.append(p1)

    sexp_stack = [sexp]
    op_stack = [handle_sexp]
    while len(op_stack) > 0:
        op = op_stack.pop()
        op(sexp_stack, op_stack, precalculated)
    return bytes32(sexp_stack[0])
