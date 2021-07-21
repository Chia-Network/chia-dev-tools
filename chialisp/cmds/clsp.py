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

@click.group("clsp", short_help="commands to use when developing chialisp")
def clsp_cmd():
    pass

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

@clsp_cmd.command("build", short_help="Build all CLVM files in a directory")
@click.argument("files", nargs=-1, required=False, default=None)
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


@clsp_cmd.command("disassemble", short_help="Disassemble serialized clvm into human readable form.")
@click.argument("files", nargs=-1, required=True)
def disassemble_cmd(files):
    for f in files:
        if len(files) > 1:
            prefix = '%s:\n' % f
        else:
            prefix = ''
        se = sexp_from_stream(io.BytesIO(bytes.fromhex(open(f).read())), lambda x: x)
        print('%s%s' % (prefix, disassemble(SExp.to(se))))

@clsp_cmd.command("treehash", short_help="Return the tree hash of a clvm file or string")
@click.argument("program", nargs=1, required=True)
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

@clsp_cmd.command("curry", short_help="Curry a program with specified arguments", cls=OrderedParamsCommand)
@click.argument("program", nargs=1, required=True)
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

@clsp_cmd.command("retrieve", short_help="Copy the specified .clib file to the current directory (for example sha256tree)")
@click.argument("libraries", nargs=-1, required=True)
def retrieve_cmd(libraries):
    import chialisp.clibs as clibs
    for lib in libraries:
        if lib[-5:] == ".clib":
            lib = lib[:-5]
        src_path = Path(clibs.__file__).parent.joinpath(f"{lib}.clib")
        shutil.copyfile(src_path, Path(os.getcwd()).joinpath(f"{lib}.clib"))