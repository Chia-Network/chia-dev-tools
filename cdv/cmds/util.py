from __future__ import annotations

import re
from typing import Dict, Iterable, List, Union

from chia.types.blockchain_format.program import Program
from clvm_tools.binutils import assemble
from clvm_tools.clvmc import compile_clvm_text


# This is do trick inspect commands into thinking they're commands
def fake_context() -> Dict:
    ctx = {"obj": {"json": True}}
    return ctx


# The clvm loaders in this library automatically search for includable files in the directory './include'
def append_include(search_paths: Iterable[str]) -> List[str]:
    if search_paths:
        search_list = list(search_paths)
        search_list.append("./include")
        return search_list
    else:
        return ["./include"]


# This is used in many places to go from CLI string -> Program object
def parse_program(program: Union[str, Program], include: Iterable = []) -> Program:
    if isinstance(program, Program):
        return program
    else:
        if "(" in program:  # If it's raw clvm
            prog: Program = Program.to(assemble(program))
        elif "." not in program:  # If it's a byte string
            prog = Program.fromhex(program)
        else:  # If it's a file
            with open(program, "r") as file:
                filestring: str = file.read()
                if "(" in filestring:  # If it's not compiled
                    # TODO: This should probably be more robust
                    if re.compile(r"\(mod\s").search(filestring):  # If it's Chialisp
                        prog = Program.to(compile_clvm_text(filestring, append_include(include)))
                    else:  # If it's CLVM
                        prog = Program.to(assemble(filestring))
                else:  # If it's serialized CLVM
                    prog = Program.fromhex(filestring)
        return prog
