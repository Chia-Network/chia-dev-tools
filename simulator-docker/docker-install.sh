#!/usr/bin/env bash

# create virtualenv and activate it.
python3 -m venv venv
ln -s venv/bin/activate .
# shellcheck disable=SC1091
. ./activate
# upgrade and install pip and wheel
python -m pip install --upgrade pip
python -m pip install wheel

# install chia-dev-tools
python -m pip install .
# install chia-blockchain in venv
python -m pip install /chia-blockchain
