import blspy

from lib.std.types.sized_bytes import bytes32


def std_hash(b) -> bytes32:
    """
    The standard hash used in many places.
    """
    return bytes32(blspy.Util.hash256(bytes(b)))

def std_literal_tree_hash(literal) -> bytes32:
    return std_hash((bytes.fromhex("01") + literal))
