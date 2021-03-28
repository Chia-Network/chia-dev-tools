from lib.std.types.ints import uint64

def float_to_timestamp(time: float) -> uint64:
    return uint64(int(time))
