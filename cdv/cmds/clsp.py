import click
import os
import io
import shutil
import re

from pathlib import Path

from clvm.SExp import SExp
from clvm.serialize import sexp_from_stream

from clvm_tools.clvmc import compile_clvm, compile_clvm_text
from clvm_tools.binutils import disassemble, assemble

from chia.types.blockchain_format.program import Program
from chia.util.byte_types import hexstr_to_bytes

from cdv.cmds.util import parse_program, append_include

@click.group("clsp", short_help="Commands to use when developing with chialisp")
def clsp_cmd():
    pass

@clsp_cmd.command("build", short_help="Build all specified CLVM files (i.e mypuz.clsp or ./puzzles/*.clsp)")
@click.argument("files", nargs=-1, required=True, default=None)
@click.option("-i","--include", required=False, multiple=True, help="Paths to search for include files (./include will be searched automatically)")
def build_cmd(files, include) -> None:
    project_path = Path.cwd()
    clvm_files = []
    for glob in files:
        for path in Path(project_path).rglob(glob):
            if path.is_dir():
                for clvm_path in Path(path).rglob('*.cl[vs][mp]'):
                    clvm_files.append(clvm_path)
            else:
                clvm_files.append(path)

    for filename in clvm_files:
        hex_file_name = (filename.name + ".hex")
        full_hex_file_name = Path(filename.parent).joinpath(hex_file_name)
        if not (full_hex_file_name.exists() and full_hex_file_name.stat().st_mtime > filename.stat().st_mtime):
            outfile = str(filename) + ".hex"
            try:
                print("Beginning compilation of "+filename.name+"...")
                compile_clvm(str(filename),outfile, search_paths=append_include(include))
                print("...Compilation finished")
            except Exception as e:
                print("Couldn't build "+filename.name+": "+str(e))


@clsp_cmd.command("disassemble", short_help="Disassemble serialized clvm into human readable form.")
@click.argument("programs", nargs=-1, required=True)
def disassemble_cmd(programs):
    for program in programs:
        print(disassemble(parse_program(program)))

@clsp_cmd.command("treehash", short_help="Return the tree hash of a clvm file or string")
@click.argument("program", nargs=1, required=True)
@click.option("-i","--include", required=False, multiple=True, help="Paths to search for include files (./include will be searched automatically)")
def treehash_cmd(program: str, include):
    print(parse_program(program, include).get_tree_hash())

@clsp_cmd.command("curry", short_help="Curry a program with specified arguments")
@click.argument("program", required=True)
@click.option("-a","--args", multiple=True, help="An argument to be curried in (i.e. -a 0xdeadbeef -a '(a 2 3)')")
@click.option("-H","--treehash", is_flag=True, help="Output the tree hash of the curried puzzle")
@click.option("-x","--dump", is_flag=True, help="Output the hex serialized program rather that the CLVM form")
@click.option("-i","--include", required=False, multiple=True, help="Paths to search for include files (./include will be searched automatically)")
def curry_cmd(program, args, treehash, dump, include):
    prog = parse_program(program, include)
    curry_args = [assemble(arg) for arg in args]

    prog_final = prog.curry(*curry_args)
    if treehash:
        print(prog_final.get_tree_hash())
    elif dump:
        print(prog_final)
    else:
        print(disassemble(prog_final))

@clsp_cmd.command("retrieve", short_help="Copy the specified .clib file to the current directory (for example sha256tree)")
@click.argument("libraries", nargs=-1, required=True)
def retrieve_cmd(libraries):
    import cdv.clibs as clibs
    for lib in libraries:
        if lib[-5:] == ".clib":
            lib = lib[:-5]
        src_path = Path(clibs.__file__).parent.joinpath(f"{lib}.clib")
        include_path = Path(os.getcwd()).joinpath("include")
        if not include_path.exists():
            os.mkdir("include")
        if src_path.exists():
            shutil.copyfile(src_path, include_path.joinpath(f"{lib}.clib"))
        else:
            print(f"Could not find {lib}.clib. You can always create it in ./include yourself.")