import re

from chia.types.blockchain_format.program import Program
from chia.util.byte_types import hexstr_to_bytes

from clvm_tools.clvmc import compile_clvm_text
from clvm_tools.binutils import assemble

def fake_context():
    ctx = {}
    ctx["obj"] = {"json": True}
    return ctx

def append_include(search_paths):
    if search_paths:
        search_list = list(search_paths)
        search_list.append("./include")
        return search_list
    else:
        return ['./include']

def parse_program(program: str, include=[]):
    if '(' in program:
        prog = Program.to(assemble(program))
    elif '.' not in program:
        prog = Program.from_bytes(hexstr_to_bytes(program))
    else:
        with open(program, "r") as file:
            filestring = file.read()
            if '(' in filestring:
                # TODO: This should probably be more robust
                if re.compile('\(mod\s').search(filestring):
                    prog = Program.to(compile_clvm_text(filestring, append_include(include)))
                else:
                    prog = Program.to(assemble(filestring))
            else:
                prog = Program.from_bytes(hexstr_to_bytes(filestring))
    return prog