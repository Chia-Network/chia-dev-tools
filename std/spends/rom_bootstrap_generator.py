from lib.std.types.program import SerializedProgram

from lib.std.util.load_clvm import load_clvm

MOD = SerializedProgram.from_bytes(load_clvm("./lib/std/clvm/rom_bootstrap_generator.clvm").as_bin())


def get_generator():
    return MOD
