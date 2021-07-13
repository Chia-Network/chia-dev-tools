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

from clvm_tools.clvmc import compile_clvm
from clvm.SExp import SExp, to_sexp_type
from clvm.serialize import sexp_from_stream
from clvm_tools.binutils import disassemble

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
    print("version")

# @cli.command("init", short_help="Initialize a skeleton project")
# def init_cmd() -> None:
#     project_path = Path.cwd()
#     script_root = Path(__file__).parent
#     project_path_lib = Path(project_path).joinpath("lib")
#     project_path_std = Path(project_path_lib).joinpath("chialisp")
#     if not project_path_lib.exists():
#         os.mkdir(project_path_lib)
#     if project_path_std.exists() :
#         shutil.rmtree(project_path_std)
#     shutil.copytree(Path(script_root).joinpath("chialisp"),project_path_std)
#     shutil.copy(Path(script_root).joinpath("chialisp").joinpath("setup.py"),project_path)
#     os.remove(Path(project_path_std).joinpath("setup.py"))

@click.argument("files", nargs=-1, required=False, default=None)
@cli.command("build", short_help="Build all CLVM files in a directory")
def build_cmd(files) -> None:
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
                compile_clvm(str(filename),outfile)
                print("...Compilation finished")
            except Exception as e:
                print("Couldn't build "+filename+": "+e)
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
def test_cmd():
    pytest.main(["./tests"])

def main() -> None:
    monkey_patch_click()
    cli()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    main()
