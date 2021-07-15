import click
import pytest
import os
import io
import sys
import shutil
from pathlib import Path
import hashlib
import re
import subprocess
import unittest

from chialisp import __version__

from clvm_tools.clvmc import compile_clvm, compile_clvm_text
from clvm.SExp import SExp, to_sexp_type
from clvm.serialize import sexp_from_stream
from clvm_tools.binutils import disassemble, assemble

from chia.util.bech32m import encode_puzzle_hash, decode_puzzle_hash
from chia.types.blockchain_format.program import Program

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

def monkey_patch_click() -> None:
    # this hacks around what seems to be an incompatibility between the python from `pyinstaller`
    # and `click`
    #
    # Not 100% sure on the details, but it seems that `click` performs a check on start-up
    # that `codecs.lookup(locale.getpreferredencoding()).name != 'ascii'`, and refuses to start
    # if it's not. The python that comes with `pyinstaller` fails this check.
    #
    # This will probably cause problems with the command-line tools that use parameters that
    # are not strict ascii. The real fix is likely with the `pyinstaller` python.

    import click.core

    click.core._verify_python3_env = lambda *args, **kwargs: 0  # type: ignore


@click.group(
    help=f"\n  Dev tooling for Chialisp development \n",
    epilog="Make a new directory and try chialisp init",
    context_settings=CONTEXT_SETTINGS,
)

@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)

@cli.command("version", short_help="Show chialisp version")
def version_cmd() -> None:
    print(__version__)

@click.argument("files", nargs=-1, required=False, default=None)
@cli.command("build", short_help="Build all CLVM files in a directory")
@click.option("-i","--include", required=False, multiple=True)
def build_cmd(files, include) -> None:
    project_path = Path.cwd()
    clvm_files = list(filter(lambda path: "venv" not in str(path), list(Path(project_path).rglob("*.[cC][lL][vV][mM]"))))
    #Adjust for building only one file
    if files:
        clvm_files = list(filter(lambda e: e.name in files, clvm_files))

    for filename in clvm_files:
        hex_file_name = (filename.name + ".hex")
        full_hex_file_name = Path(filename.parent).joinpath(hex_file_name)
        if not (full_hex_file_name.exists() and full_hex_file_name.stat().st_mtime > filename.stat().st_mtime):
            outfile = str(filename) + ".hex"
            try:
                print("Beginning compilation of "+filename.name+"...")
                compile_clvm(str(filename),outfile, search_paths=include)
                print("...Compilation finished")
            except Exception as e:
                print("Couldn't build "+filename.name+": "+e)
                pass


@click.argument("files", nargs=-1, required=True)
@cli.command("disassemble", short_help="Disassemble serialized clvm into human readable form.")
def disassemble_cmd(files):
    for f in files:
        if len(files) > 1:
            prefix = '%s:\n' % f
        else:
            prefix = ''
        se = sexp_from_stream(io.BytesIO(bytes.fromhex(open(f).read())), lambda x: x)
        print('%s%s' % (prefix, disassemble(SExp.to(se))))

@cli.command("test", short_help="Run the local test suite (located in ./tests)")
@click.option("-d", "--discover", is_flag=True, type=bool, help="List the tests without running them")
def test_cmd(discover: bool):
    if discover:
        pytest.main(["--collect-only","./tests"])
    else:
        pytest.main(["./tests"])

@click.argument("puzzle_hash", nargs=1, required=True)
@cli.command("encode", short_help="Encode a puzzle hash to a bech32m address")
@click.option("-p", "--prefix", type=str, default="xch", show_default=True, required=False)
def encode_cmd(puzzle_hash, prefix):
    print(encode_puzzle_hash(bytes.fromhex(puzzle_hash), prefix))

@click.argument("address", nargs=1, required=True)
@cli.command("decode", short_help="Decode a bech32m address to a puzzle hash")
def encode_cmd(address):
    print(decode_puzzle_hash(address).hex())

def parse_program(program: str):
    if '(' in program:
        prog = Program.to(assemble(program))
    elif '.' not in program:
        prog = Program.from_bytes(bytes.fromhex(program))
    else:
        with open(program, "r") as file:
            filestring = file.read()
            if '(' in filestring:
                if re.compile('\(mod\s').search(filestring):
                    prog = Program.to(compile_clvm_text(filestring, ['.']))
                else:
                    prog = Program.to(assemble(filestring))
            else:
                prog = Program.from_bytes(bytes.fromhex(filestring))
    return prog

@click.argument("program", nargs=1, required=True)
@cli.command("treehash", short_help="Return the tree hash of a clvm file or string")
def treehash_cmd(program: str):
    print(parse_program(program).get_tree_hash())

class OrderedParamsCommand(click.Command):
    _options = []
    def parse_args(self, ctx, args):
        # run the parser for ourselves to preserve the passed order
        parser = self.make_parser(ctx)
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            if param.name not in ('program', 'treehash'):
                type(self)._options.append((param, opts[param.name].pop(0)))

        # return "normal" parse results
        return super().parse_args(ctx, args)

@click.argument("program", nargs=1, required=True)
@cli.command("curry", short_help="Curry a program with specified arguments", cls=OrderedParamsCommand)
@click.option("-b","--bytes", type=str, required=False, multiple=True)
@click.option("-s","--string", type=str, required=False, multiple=True)
@click.option("-i","--integer", type=int, required=False, multiple=True)
@click.option("-p","--prog", type=str, required=False, multiple=True)
@click.option("-th","--treehash", is_flag=True, type=bool, help="Return the tree hash of the program")
def curry_cmd(*, program: str, **kwargs):
    prog = parse_program(program)
    curry_args = []
    for param, value in OrderedParamsCommand._options:
        if param.name == 'bytes':
            curry_args.append(bytes.fromhex(value))
        elif param.name == 'string':
            curry_args.append(value)
        elif param.name == 'integer':
            curry_args.append(int(value))
        elif param.name == 'prog':
            curry_args.append(parse_program(value))

    prog_final = prog.curry(*curry_args)
    if kwargs["treehash"]:
        print(prog_final.get_tree_hash())
    else:
        print(prog_final)


def main() -> None:
    monkey_patch_click()
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
