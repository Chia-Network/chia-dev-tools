Chia Dev Tools
=======

Install
-------

Initialize a new project directory and `cd` into it. Then follow the following instructions to get set up:

**Ubuntu/MacOSs**
```
python3 -m venv venv
. ./venv/bin/activate
pip install --extra-index-url https://pypi.chia.net/simple/ chia-dev-tools
cdv --version
```
(If you're on an M1 Mac, make sure you are running an ARM64 native python virtual environment)

**Windows Powershell**

Requires: Installation of [Python 3 for Windows](https://www.python.org/downloads/windows/)

```
py -m venv venv
./venv/Scripts/activate
pip install --extra-index-url https://pypi.chia.net/simple/ chia-dev-tools
cdv --version
```

**From Source**

Alternatively, you can clone the repo, and install from source:
```
git clone https://github.com/Chia-Network/chia-dev-tools.git
cd chia-dev-tools
# The following for Linux/MacOS
python3 -m venv venv
. ./venv/bin/activate
# The following for Windows
py -m venv venv
./venv/Scripts/activate
# To install chia-dev-tools
pip install --extra-index-url https://pypi.chia.net/simple/ .
```

What's in it?
-------------

This python wheel will bring in commands from other chia repositories such as `brun` or even `chia`!

The command unique to this repository is `cdv`. Run `cdv --help` to see what it does:

```
Usage: cdv [OPTIONS] COMMAND [ARGS]...

  Dev tooling for Chia development

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  clsp     Commands to use when developing with chialisp
  decode   Decode a bech32m address to a puzzle hash
  encode   Encode a puzzle hash to a bech32m address
  hash     SHA256 hash UTF-8 strings or bytes (use 0x prefix for bytes)
  inspect  Inspect various data structures
  rpc      Make RPC requests to a Chia full node
  test     Run the local test suite (located in ./tests)
```

Tests
----------

The test command allows you to initialize and run local tests.
```
cdv test
```

Optionally, to make new tests, you can bootstrap the creation of a test file by running:
```
cdv test --init
# Make changes to the ./tests/test_skeleton.py file
cdv test
```


Chialisp Commands
-----------------

The `clsp` family of commands are helpful when writing, building, and hashing Chialisp and CLVM programs.

```
cdv clsp build ./puzzles/password.clsp
cdv clsp retrieve condition_codes sha256tree
cdv clsp treehash '(a 2 3)'
cdv clsp curry ./puzzles/password.clsp.hex -a 0xdeadbeef -a "(q . 'I'm an inner puzzle!')"
cdv clsp disassemble ff0180
```

Inspect Commands
----------------

The `inspect` family of commands allows you to build and examine certain Chia related objects

```
cdv inspect -id coins --parent-id e16dbc782f500aa24891886779067792b3305cff8b873ae1e77273ad0b7e6c05 --puzzle-hash e16dbc782f500aa24891886779067792b3305cff8b873ae1e77273ad0b7e6c05 --amount 123
cdv inspect --json spends --coin ./coin.json --puzzle-reveal ff0180 --solution '()'
cdv inspect --bytes spendbundles ./spend_bundle.json
cdv inspect --json any 0e1074f76177216b011668c35b1496cbd10eff5ae43f6a7924798771ac131b0a0e1074f76177216b011668c35b1496cbd10eff5ae43f6a7924798771ac131b0a0000000000000001ff018080
```

RPC Commands
------------

There are also commands for interacting with the full node's RPC endpoints (in development, more to come).  The family of commands finds the full node the same way that the `chia` commands do.  Make sure to have a local node running before you try these.

```
cdv rpc state
cdv rpc blocks -s 0 -e 1
cdv rpc coinrecords --by id 6ce8fa56321d954f54ba27e58f4a025eb1081d2e1f38fc089a2e72927bcde0d1
cdv rpc pushtx ./spend_bundle.json
```

Python Packages
---------------

Being in a virtual environment with this tool will also give your python programs access to all of the chia repository packages.
It also comes with a package of its own that lives in the `cdv` namespace with some helpful utilities.  Of particular interest is the `cdv.test` package which comes with all sorts of tools to help you write lifecycle tests of smart coins.  Check out [the examples](https://github.com/Chia-Network/chia-dev-tools/tree/main/cdv/examples) to see it in action.
