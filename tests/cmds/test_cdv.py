from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner, Result

from cdv.cmds.cli import cli


class TestCdvCommands:
    def test_encode_decode(self):
        runner = CliRunner()
        puzhash: str = "3d4237d9383a7b6e60d1bfe551139ec2d6e5468205bf179ed381e66bed7b9788"

        # Without prefix
        result: Result = runner.invoke(cli, ["encode", puzhash])
        address: str = "xch184pr0kfc8fakucx3hlj4zyu7cttw235zqkl308kns8nxhmtmj7yqxsnauc"
        assert result.exit_code == 0
        assert address in result.output
        result = runner.invoke(cli, ["decode", address])
        assert result.exit_code == 0
        assert puzhash in result.output

        # With prefix
        result = runner.invoke(cli, ["encode", puzhash, "--prefix", "txch"])
        test_address: str = "txch184pr0kfc8fakucx3hlj4zyu7cttw235zqkl308kns8nxhmtmj7yqth5tat"
        assert result.exit_code == 0
        assert test_address in result.output
        result = runner.invoke(cli, ["decode", test_address])
        assert result.exit_code == 0
        assert puzhash in result.output

    def test_hash(self):
        runner = CliRunner()
        str_msg: str = "chia"
        b_msg: str = "0xcafef00d"

        result: Result = runner.invoke(cli, ["hash", str_msg])
        assert result.exit_code == 0
        assert "3d4237d9383a7b6e60d1bfe551139ec2d6e5468205bf179ed381e66bed7b9788" in result.output
        result = runner.invoke(cli, ["hash", b_msg])
        assert result.exit_code == 0
        assert "8f6e594e007ca1a1676ef64469c58f7ece8cddc9deae0faf66fbce2466519ebd" in result.output

    def test_test(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result: Result = runner.invoke(cli, ["test", "--init"])
            assert result.exit_code == 0
            assert Path("./tests").exists() and Path("./tests/test_skeleton.py").exists()

            # 2023-10-17 Commenting subsequent tests because pytest throws an import file mismatch error
            # It seems that the test_skeleton module is being imported from the test enviroment but is
            # also present in the tests directory, causing the mismatch.
            # This repo has a tool (build-init-files.py) for creating missing __init__ files which may
            # have been intended as a solution to this problem, but as of now it doesn't work.

            # result = runner.invoke(cli, ["test", "--discover"])
            # assert result.exit_code == 0
            # assert "TestSomething" in result.output

            # result = runner.invoke(cli, ["test"])
            # assert result.exit_code == 0
            # assert "test_skeleton.py ." in result.output
