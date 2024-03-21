from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from click.testing import CliRunner, Result

from cdv.cmds.cli import cli

EMPTY_SIG = "c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"  # noqa


class TestInspectCommands:
    def test_any(self):
        runner = CliRunner()

        # Try to inspect a program
        result: Result = runner.invoke(cli, ["inspect", "any", "ff0101"])
        assert result.exit_code == 0
        assert "guess" not in result.output

        # Try to inspect a private key
        result = runner.invoke(
            cli,
            [
                "inspect",
                "any",
                "05ec9428fc2841a79e96631a633b154b57a45311c0602269a6500732093a52cd",
            ],
        )
        assert result.exit_code == 0
        assert "guess" not in result.output

        # Try to inspect a public key
        result = runner.invoke(
            cli,
            [
                "inspect",
                "any",
                "b364a088d9df9423e54bff4c62e4bd854445fb8f5b8f6d80dea06773a4f828734a3a75318b180364ca8468836f0742db",
            ],
        )
        assert result.exit_code == 0
        assert "guess" not in result.output

        # Try to inspect an aggsig
        result = runner.invoke(
            cli,
            [
                "inspect",
                "any",
                EMPTY_SIG,
            ],
        )
        assert result.exit_code == 0
        assert "guess" not in result.output

        for class_type in ["coinrecord", "coin", "spendbundle", "spend"]:
            valid_json_path = Path(__file__).parent.joinpath(f"object_files/{class_type}s/{class_type}.json")
            invalid_json_path = Path(__file__).parent.joinpath(f"object_files/{class_type}s/{class_type}_invalid.json")
            metadata_path = Path(__file__).parent.joinpath(f"object_files/{class_type}s/{class_type}_metadata.json")
            valid_json: Dict = json.loads(open(valid_json_path, "r").read())
            metadata_json: Dict = json.loads(open(metadata_path, "r").read())

            # Try to load the invalid and make sure it fails
            result = runner.invoke(cli, ["inspect", "any", str(invalid_json_path)])
            assert result.exit_code == 0
            # If this succeeds, there should be no file name, if it fails, the file name should be output as info
            assert str(invalid_json_path) in result.output

            # Try to load the valid json
            result = runner.invoke(cli, ["inspect", "any", json.dumps(valid_json)])
            assert result.exit_code == 0
            for key in valid_json.keys():
                key_type = type(valid_json[key])
                if (key_type is not dict) and (key_type is not list):
                    assert (str(valid_json[key]) in result.output) or (str(valid_json[key]).lower() in result.output)

            # Try to load bytes
            if class_type != "coin":
                valid_hex_path = Path(__file__).parent.joinpath(f"object_files/{class_type}s/{class_type}.hex")

                # From a file
                result = runner.invoke(cli, ["inspect", "--json", "any", str(valid_hex_path)])
                assert result.exit_code == 0
                assert '"coin":' in result.output

                # From a string
                valid_hex: str = open(valid_hex_path, "r").read()
                result = runner.invoke(cli, ["inspect", "--json", "any", valid_hex])
                assert result.exit_code == 0
                assert '"coin":' in result.output

            # Make sure the ID calculation is correct
            result = runner.invoke(cli, ["inspect", "--id", "any", str(valid_json_path)])
            assert result.exit_code == 0
            assert metadata_json["id"] in result.output

            # Make sure the bytes encoding is correct
            result = runner.invoke(cli, ["inspect", "--bytes", "any", str(valid_json_path)])
            assert result.exit_code == 0
            assert metadata_json["bytes"] in result.output

            # Make sure the type guessing is correct
            result = runner.invoke(cli, ["inspect", "--type", "any", str(valid_json_path)])
            assert result.exit_code == 0
            assert metadata_json["type"] in result.output

    def test_coins(self):
        pid: str = "0x0000000000000000000000000000000000000000000000000000000000000000"
        ph: str = "0000000000000000000000000000000000000000000000000000000000000000"
        amount: str = "0"
        id: str = "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b"

        runner = CliRunner()
        result: Result = runner.invoke(cli, ["inspect", "--id", "coins", "-pid", pid, "-ph", ph, "-a", amount])
        assert result.exit_code == 0
        assert id in result.output

    def test_spends(self):
        coin_path = Path(__file__).parent.joinpath("object_files/coins/coin.json")
        pid: str = "0x0000000000000000000000000000000000000000000000000000000000000000"
        ph: str = "0000000000000000000000000000000000000000000000000000000000000000"
        amount: str = "0"
        id: str = "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b"
        puzzle_reveal: str = "01"
        solution: str = "80"
        cost: str = "569056"
        modified_cost: str = "557056"

        runner = CliRunner()

        # Specify the coin file
        result: Result = runner.invoke(
            cli,
            [
                "inspect",
                "--id",
                "spends",
                "-c",
                str(coin_path),
                "-pr",
                puzzle_reveal,
                "-s",
                solution,
            ],
        )
        assert result.exit_code == 0
        assert id in result.output

        # Specify all of the arguments
        base_command: List[str] = [
            "inspect",
            "--id",
            "spends",
            "-pid",
            pid,
            "-ph",
            ph,
            "-a",
            amount,
            "-pr",
            puzzle_reveal,
            "-s",
            solution,
        ]
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert id in result.output

        # Ask for the cost
        base_command.append("-ec")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert id in result.output
        assert cost in result.output

        # Change the cost per byte
        base_command.append("--ignore-byte-cost")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert id in result.output
        assert modified_cost in result.output

    def test_spendbundles(self):
        spend_path = Path(__file__).parent.joinpath("object_files/spends/spend.json")
        spend_path_2 = Path(__file__).parent.joinpath("object_files/spends/spend_2.json")
        pubkey: str = "80df54b2a616f5c79baaed254134ae5dfc6e24e2d8e1165b251601ceb67b1886db50aacf946eb20f00adc303e7534dd0"
        signable_data: str = (
            "24f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4bccd5bb71183532bff220ba46c268991a3ff07eb358e8255a65c30a2dce0e5fbb"  # noqa
        )
        agg_sig: str = (
            "b83fe374efbc5776735df7cbfb7e27ede5079b41cd282091450e4de21c4b772e254ce906508834b0c2dcd3d58c47a96914c782f0baf8eaff7ece3b070d2035cd878f744deadcd6c6625c1d0a1b418437ee3f25c2df08ffe08bdfe06b8a83b514"  # noqa
        )
        id_no_sig: str = "3fc441c1048a4e0b9fd1648d7647fdebd220cf7dd51b6967dcaf76f7043e83d6"
        id_with_sig: str = "7d6f0da915deed117ad5589aa8bd6bf99beb69f48724b14b2134f6f8af6d8afc"
        network_modifier: str = "testnet7"
        modified_signable_data: str = (
            "24f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b117816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015af"  # noqa
        )
        cost: str = "6692283"
        modified_cost: str = "6668283"

        runner = CliRunner()

        # Build with only the spends
        result: Result = runner.invoke(
            cli,
            [
                "inspect",
                "--id",
                "spendbundles",
                "-s",
                str(spend_path),
                "-s",
                str(spend_path_2),
            ],
        )
        assert result.exit_code == 0
        assert id_no_sig in result.output

        # Build with the aggsig as well
        base_command: List[str] = [
            "inspect",
            "--id",
            "spendbundles",
            "-s",
            str(spend_path),
            "-s",
            str(spend_path_2),
            "-as",
            agg_sig,
        ]
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert id_with_sig in result.output

        # Test that debugging info comes up
        base_command.append("-db")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert "Debugging Information" in result.output

        # Make sure our signable data comes out
        base_command.append("-sd")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert pubkey in result.output
        assert result.output.count(signable_data) == 2

        # Try a different network for different signable data
        base_command.append("-n")
        base_command.append(network_modifier)
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert modified_signable_data in result.output

        # Output the execution cost
        base_command.append("-ec")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert cost in result.output

        # Try a new cost per bytes
        base_command.append("--ignore-byte-cost")
        result = runner.invoke(cli, base_command)
        assert result.exit_code == 0
        assert modified_cost in result.output

        # Try to use it the programmatic way (like cdv rpc pushtx does)
        from cdv.cmds.chia_inspect import do_inspect_spend_bundle_cmd
        from cdv.cmds.util import fake_context

        bundle_path = Path(__file__).parent.joinpath("object_files/spendbundles/spendbundle.json")
        assert len(do_inspect_spend_bundle_cmd(fake_context(), [str(bundle_path)], print_results=False)) > 0

    def test_coinrecords(self):
        coin_path = Path(__file__).parent.joinpath("object_files/coins/coin.json")
        pid: str = "0x0000000000000000000000000000000000000000000000000000000000000000"
        ph: str = "0000000000000000000000000000000000000000000000000000000000000000"
        amount: str = "0"
        id: str = "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b"
        coinbase: str = "False"
        confirmed_block_index: str = "500"
        spent_block_index: str = "501"
        timestamp: str = "909469800"

        runner = CliRunner()

        # Try to load it from a file
        record_path = Path(__file__).parent.joinpath("object_files/coinrecords/coinrecord.json")
        result: Result = runner.invoke(cli, ["inspect", "coinrecords", str(record_path)])
        assert result.exit_code == 0
        assert '"coin":' in result.output

        # Specify the coin file
        result = runner.invoke(
            cli,
            [
                "inspect",
                "--id",
                "coinrecords",
                "-c",
                str(coin_path),
                "-cb",
                coinbase,
                "-ci",
                confirmed_block_index,
                "-si",
                spent_block_index,
                "-t",
                timestamp,
            ],
        )
        assert result.exit_code == 0
        assert id in result.output

        # Specify all of the arguments
        result = runner.invoke(
            cli,
            [
                "inspect",
                "--id",
                "coinrecords",
                "-pid",
                pid,
                "-ph",
                ph,
                "-a",
                amount,
                "-cb",
                coinbase,
                "-ci",
                confirmed_block_index,
                "-si",
                spent_block_index,
                "-t",
                timestamp,
            ],
        )
        assert result.exit_code == 0
        assert id in result.output

    def test_programs(self):
        program: str = "ff0101"
        id: str = "69ae360134b1fae04326e5546f25dc794a19192a1f22a44a46d038e7f0d1ecbb"

        runner = CliRunner()

        result: Result = runner.invoke(cli, ["inspect", "--id", "programs", program])
        assert result.exit_code == 0
        assert id in result.output

    def test_keys(self):
        mnemonic: str = (
            "spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend spend"  # noqa
        )
        sk: str = "1ef0ff42df2fdd4472312e033f555c569d18b85ba0d9f1b09ed87b254dc18a8e"
        pk: str = "ae6c7589432cb60a00d84fc83971f50a98fd728863d3ceb189300f2f80d6839e9a2e761ef6cdce809caee83a4e73b623"
        hd_modifier: str = "m/12381/8444/0/0"
        type_modifier: str = "farmer"  # Should be same as above HD Path
        farmer_sk: str = "6a97995a8b35c69418ad60152a5e1c9a32d159bcb7c343c5ccf83c71e4df2038"
        synthetic_sk: str = "4272b71ba1c628948e308148e92c1a9b24a785d52f604610a436d2088f72d578"
        ph_modifier: str = "69ae360134b1fae04326e5546f25dc794a19192a1f22a44a46d038e7f0d1ecbb"
        modified_synthetic_sk: str = "405d969856846304eec6b243d810665cb3b7e94b56747b87e8e5597948ba1da6"

        runner = CliRunner()

        # Build the key from secret key
        result: Result = runner.invoke(cli, ["inspect", "keys", "-sk", sk])
        assert result.exit_code == 0
        assert sk in result.output
        assert pk in result.output
        key_output: str = result.output

        # Build the key from mnemonic
        result = runner.invoke(cli, ["inspect", "keys", "-m", mnemonic])
        assert result.exit_code == 0
        assert result.output == key_output

        # Use only the public key
        result = runner.invoke(cli, ["inspect", "keys", "-pk", pk])
        assert result.exit_code == 0
        assert result.output in key_output

        # Generate a random one
        result = runner.invoke(cli, ["inspect", "keys", "--random"])
        assert result.exit_code == 0
        assert "Secret Key" in result.output
        assert "Public Key" in result.output

        # Check the HD derivation is working
        result = runner.invoke(cli, ["inspect", "keys", "-sk", sk, "-hd", hd_modifier])
        assert result.exit_code == 0
        assert farmer_sk in result.output

        # Check the type derivation is working
        result = runner.invoke(cli, ["inspect", "keys", "-sk", sk, "-t", type_modifier])
        assert result.exit_code == 0
        assert farmer_sk in result.output

        # Check that synthetic calculation is working
        result = runner.invoke(cli, ["inspect", "keys", "-sk", sk, "-sy"])
        assert result.exit_code == 0
        assert synthetic_sk in result.output

        # Check that using a non default puzzle hash is working
        result = runner.invoke(cli, ["inspect", "keys", "-sk", sk, "-sy", "-ph", ph_modifier])
        assert result.exit_code == 0
        assert modified_synthetic_sk in result.output

    def test_signatures(self):
        secret_key_1: str = "70432627e84c13c1a6e6007bf6d9a7a0342018fdef7fc911757aad5a6929d20a"
        secret_key_2: str = "0f01f7f68935f8594548bca3892fec419c6b2aa7cff54c3353a2e9b1011f09c7"
        text_message: str = "cafe food"
        bytes_message: str = "0xcafef00d"
        extra_signature: str = (
            "b5d4e653ec9a737d19abe9af7050d37b0f464f9570ec66a8457fbdabdceb50a77c6610eb442ed1e4ace39d9ecc6d40560de239c1c8f7a115e052438385d594be7394df9287cf30c3254d39f0ae21daefc38d3d07ba3e373628bf8ed73f074a80"  # noqa
        )
        final_signature: str = (
            "b7a6ab2c825068eb40298acab665f95c13779e828d900b8056215b54e47d8b8314e8b61fbb9c98a23ef8a134155a35b109ba284bd5f1f90f96e0d41427132b3ca6a83faae0806daa632ee6b1602a0b4bad92f2743fdeb452822f0599dfa147c0"  # noqa
        )

        runner = CliRunner()

        # Test that an empty command returns an empty signature
        result = runner.invoke(cli, ["inspect", "signatures"])
        assert result.exit_code == 0
        assert EMPTY_SIG in result.output

        # Test a complex signature calculation
        result = runner.invoke(
            cli,
            [
                "inspect",
                "signatures",
                "-sk",
                secret_key_1,
                "-t",
                text_message,
                "-sk",
                secret_key_2,
                "-b",
                bytes_message,
                "-sig",
                extra_signature,
            ],
        )
        assert result.exit_code == 0
        assert final_signature in result.output
