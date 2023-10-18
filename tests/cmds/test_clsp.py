from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import IO, List

from chia.types.blockchain_format.program import Program
from click.testing import CliRunner, Result
from clvm_tools.binutils import disassemble

from cdv.cmds.cli import cli


class TestClspCommands:
    program: str = "(q . 1)"
    serialized: str = "ff0101"
    mod: str = "(mod () (include condition_codes.clib) CREATE_COIN)"

    # This comes before build because build is going to use retrieve
    def test_retrieve(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result: Result = runner.invoke(cli, ["clsp", "retrieve", "condition_codes"])
            assert result.exit_code == 0
            assert Path("./include/condition_codes.clib").exists()

            result = runner.invoke(cli, ["clsp", "retrieve", "sha256tree.clib"])
            assert result.exit_code == 0
            assert Path("./include/condition_codes.clib").exists()

    def test_build(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Test building CLVM
            program_file: IO = open("program.clvm", "w")
            program_file.write(self.program)
            program_file.close()
            result: Result = runner.invoke(cli, ["clsp", "build", "."])
            assert result.exit_code == 0
            assert Path("./program.clvm.hex").exists()
            hex_output: str = open("program.clvm.hex", "r").read()
            assert "01" in hex_output
            assert len(hex_output) <= 3  # With or without newline

            # Use the retrieve command for the include file
            runner.invoke(cli, ["clsp", "retrieve", "condition_codes"])

            # Test building Chialisp (automatic include search)
            mod_file: IO = open("mod.clsp", "w")
            mod_file.write(self.mod)
            mod_file.close()
            result = runner.invoke(cli, ["clsp", "build", "./mod.clsp"])
            assert result.exit_code == 0
            assert Path("./mod.clsp.hex").exists()
            hex_output: str = open("mod.clsp.hex", "r").read()
            assert "ff0133" in hex_output
            assert len(hex_output) <= 7  # With or without newline

            # Test building Chialisp (specified include search)
            os.remove(Path("./mod.clsp.hex"))
            shutil.copytree("./include", "./include_test")
            shutil.rmtree("./include")
            result = runner.invoke(cli, ["clsp", "build", ".", "--include", "./include_test"])
            assert result.exit_code == 0
            assert Path("./mod.clsp.hex").exists()
            hex_output: str = open("mod.clsp.hex", "r").read()
            assert "ff0133" in hex_output
            assert len(hex_output) <= 7  # With or without newline

    def test_curry(self):
        integer: int = 1
        hexadecimal = bytes.fromhex("aabbccddeeff")
        string: str = "hello"
        program = Program.to([2, 2, 3])
        mod = Program.from_bytes(bytes.fromhex(self.serialized))
        curried_mod: Program = mod.curry(integer, hexadecimal, string, program)

        runner = CliRunner()
        # Curry one of each kind of argument
        cmd: List[str] = [
            "clsp",
            "curry",
            str(mod),
            "-a",
            str(integer),
            "-a",
            "0x" + hexadecimal.hex(),
            "-a",
            string,
            "-a",
            disassemble(program),
        ]

        result: Result = runner.invoke(cli, cmd)
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

    def test_uncurry(self):
        hexadecimal = bytes.fromhex("aabbccddeeff")
        mod = Program.from_bytes(bytes.fromhex(self.serialized))
        curried_mod: Program = mod.curry(hexadecimal)

        runner = CliRunner()
        # Curry one of each kind of argument
        cmd: List[str] = [
            "clsp",
            "uncurry",
            str(curried_mod),
        ]

        result: Result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert disassemble(mod) in result.output
        assert disassemble(curried_mod) not in result.output

        cmd.append("-x")
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert str(mod) in result.output
        assert str(curried_mod) not in result.output

        cmd.append("-H")
        result = runner.invoke(cli, cmd)
        assert result.exit_code == 0
        assert mod.get_tree_hash().hex() in result.output

    # The following two functions aim to test every branch of the parse_program utility function between them
    def test_disassemble(self):
        runner = CliRunner()
        # Test the program passed in as a hex string
        result: Result = runner.invoke(cli, ["clsp", "disassemble", self.serialized])
        assert result.exit_code == 0
        assert self.program in result.output
        # Test the program passed in as a hex file
        with runner.isolated_filesystem():
            program_file = open("program.clvm.hex", "w")
            program_file.write(self.serialized)
            program_file.close()
            result = runner.invoke(cli, ["clsp", "disassemble", "program.clvm.hex"])
            assert result.exit_code == 0
            assert self.program in result.output

    def test_treehash(self):
        # Test a program passed as a string
        runner = CliRunner()
        program: str = "(a 2 3)"
        program_as_mod: str = "(mod (arg . arg2) (a arg arg2))"
        program_hash: str = "530d1b3283c802be3a7bdb34b788c1898475ed76c89ecb2224e4b4f40c32d1a4"
        result: Result = runner.invoke(cli, ["clsp", "treehash", program])
        assert result.exit_code == 0
        assert program_hash in result.output

        # Test a program passed in as a CLVM file
        filename: str = "program.clvm"
        with runner.isolated_filesystem():
            program_file: IO = open(filename, "w")
            program_file.write(program)
            program_file.close()
            result = runner.invoke(cli, ["clsp", "treehash", filename])
            assert result.exit_code == 0
            assert program_hash in result.output

        # Test a program passed in as a Chialisp file
        with runner.isolated_filesystem():
            program_file: IO = open(filename, "w")
            program_file.write(program_as_mod)
            program_file.close()
            result = runner.invoke(cli, ["clsp", "treehash", filename])
            assert result.exit_code == 0
            assert program_hash in result.output

    def test_cat_puzzle_hash(self):
        runner = CliRunner()
        args_bech32m = [
            "xch18h6rmktpdgms23sqj009hxjwz7szmumwy257uzv8dnvqcuaz0ltqmu9ret",
            "-t",
            "0x7efa9f202cfd8e174e1376790232f1249e71fbe46dc428f7237a47d871a2b78b",
        ]
        expected_bech32m = "xch1wtlyxwdl99xk5war69jzxpafx4kmvcjrmevlxn4yet8r7cfc63tqww5qwg"
        args_hex = [
            "0x3df43dd9616a3705460093de5b9a4e17a02df36e22a9ee09876cd80c73a27fd6",
            "-t",
            "0x7efa9f202cfd8e174e1376790232f1249e71fbe46dc428f7237a47d871a2b78b",
        ]
        expected_hex = "72fe4339bf294d6a3ba3d1642307a9356db66243de59f34ea4cace3f6138d456"
        args_usds = ["xch16ay8wdjtl8f58gml4vl5jw4vm6ychhu3lk9hddhykhcmt6l6599s9lrvqn", "-t", "USDSC"]
        expected_usds = "xch1hurndm0nx93epskq496rt25yf5ar070wzhcdtpf3rt5gx2vu97wq4q5g3k"

        result_bech32m: Result = runner.invoke(cli, ["clsp", "cat_puzzle_hash"] + args_bech32m)
        assert result_bech32m.exit_code == 0
        assert expected_bech32m in result_bech32m.output
        result_hex: Result = runner.invoke(cli, ["clsp", "cat_puzzle_hash"] + args_hex)
        assert result_hex.exit_code == 0
        assert expected_hex in result_hex.output
        result_usds: Result = runner.invoke(cli, ["clsp", "cat_puzzle_hash"] + args_usds)
        assert result_usds.exit_code == 0
        assert expected_usds in result_usds.output
