import os
import shutil

from pathlib import Path
from click.testing import CliRunner

from chia.types.blockchain_format.program import Program

from clvm_tools.binutils import assemble, disassemble

from cdv.cmds.cli import cli

class TestCdvCommands:
    program = '(q . 1)'
    serialized = 'ff0101'
    mod = '(mod () (include condition_codes.clib) CREATE_COIN)'

    #This comes before build because build is going to use retrieve
    def test_retrieve(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["clsp", "retrieve", "condition_codes"])
            assert result.exit_code == 0
            assert Path("./include/condition_codes.clib").exists()

            result = runner.invoke(cli, ["clsp", "retrieve", "sha256tree.clib"])
            assert result.exit_code == 0
            assert Path("./include/condition_codes.clib").exists()

    def test_build(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Test building CLVM
            program_file = open("program.clvm","w")
            program_file.write(self.program)
            program_file.close()
            result = runner.invoke(cli, ["clsp","build","."])
            assert result.exit_code == 0
            assert Path("./program.clvm.hex").exists()
            assert open("program.clvm.hex","r").read() == "01"

            # Use the retrieve command for the include file
            runner.invoke(cli, ["clsp", "retrieve", "condition_codes"])

            # Test building Chialisp (automatic include search)
            mod_file = open("mod.clsp","w")
            mod_file.write(self.mod)
            mod_file.close()
            result = runner.invoke(cli, ["clsp","build","./mod.clsp"])
            assert result.exit_code == 0
            assert Path("./mod.clsp.hex").exists()
            assert open("mod.clsp.hex","r").read() == "ff0133"

            # Test building Chialisp (specified include search)
            os.remove(Path("./mod.clsp.hex"))
            shutil.copytree("./include","./include_test")
            shutil.rmtree("./include")
            result = runner.invoke(cli, ["clsp","build",".","--include","./include_test"])
            assert result.exit_code == 0
            assert Path("./mod.clsp.hex").exists()
            assert open("mod.clsp.hex","r").read() == "ff0133"

    def test_curry(self):
        integer = 1
        hexadecimal = bytes.fromhex("aabbccddeeff")
        string = "hello"
        program = Program.to([2, 2, 3])
        mod = Program.from_bytes(bytes.fromhex(self.serialized))
        curried_mod = mod.curry(integer, hexadecimal, string, program)

        runner = CliRunner()
        cmd = ["clsp","curry",str(mod),
            "-a", str(integer),
            "-a", "0x"+hexadecimal.hex(),
            "-a", string,
            "-a", disassemble(program),
        ]

        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert disassemble(curried_mod) in result.output

        cmd.append("-x")
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert str(curried_mod) in result.output

        cmd.append("-H")
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert curried_mod.get_tree_hash().hex() in result.output

    # The following two functions aim to test every branch of the parse_program utility function between them
    def test_disassemble(self):
        runner = CliRunner()
        # Test the program passed in as a hex string
        result = runner.invoke(cli, ["clsp","disassemble",self.serialized])
        assert result.exit_code == 0
        assert self.program in result.output
        # Test the program passed in as a hex file
        with runner.isolated_filesystem():
            program_file = open("program.clvm.hex","w")
            program_file.write(self.serialized)
            program_file.close()
            result = runner.invoke(cli, ["clsp","disassemble","program.clvm.hex"])
            assert result.exit_code == 0
            assert self.program in result.output

    def test_treehash(self):
        # Test a program passed as a string
        runner = CliRunner()
        program = "(a 2 3)"
        program_as_mod = "(mod (arg . arg2) (a arg arg2))"
        program_hash = "530d1b3283c802be3a7bdb34b788c1898475ed76c89ecb2224e4b4f40c32d1a4"
        result = runner.invoke(cli, ["clsp","treehash",program])
        assert result.exit_code == 0
        assert program_hash in result.output

        # Test a program passed in as a CLVM file
        filename = "program.clvm"
        with runner.isolated_filesystem():
            program_file = open(filename,"w")
            program_file.write(program)
            program_file.close()
            result = runner.invoke(cli, ["clsp","treehash",filename])
            assert result.exit_code == 0
            assert program_hash in result.output

        # Test a program passed in as a Chialisp file
        with runner.isolated_filesystem():
            program_file = open(filename,"w")
            program_file.write(program_as_mod)
            program_file.close()
            result = runner.invoke(cli, ["clsp","treehash",filename])
            assert result.exit_code == 0
            assert program_hash in result.output