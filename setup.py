#!/usr/bin/env python

from setuptools import setup, find_packages
from glob import glob
from pathlib import Path

with open("README.md", "rt") as fh:
    long_description = fh.read()

dependencies = [
    "clvm_tools>=0.4.3",
    "clvm_rs>=0.1.1",
    "chia-blockchain==1.2.3",
    # "chia-blockchain@git+https://github.com/Chia-Network/chia-blockchain.git@fa2e66bc74d07a0d79d9a3762e5207aa6d38a0de",
    "pytest",
    "pytest-asyncio",
    "pytimeparse",
]

dev_dependencies = []

setup(
    name="chia_dev_tools",
    version="1.0.1",
    packages=find_packages(),
    author="Quexington",
    entry_points={
        "console_scripts": [
            "cdv = cdv.cmds.cli:main"
        ],
    },
    package_data={
        "": ["*.clvm", "*.clvm.hex", "*.clib", "*.clsp", "*.clsp.hex"],
    },
    author_email="m.hauff@chia.net",
    setup_requires=["setuptools_scm"],
    install_requires=dependencies,
    url="https://github.com/Chia-Network",
    license="https://opensource.org/licenses/Apache-2.0",
    description="Chia development commands",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Security :: Cryptography",
    ],
    extras_require=dict(dev=dev_dependencies,),
    project_urls={
        "Bug Reports": "https://github.com/Chia-Network/chia-dev-tools",
        "Source": "https://github.com/Chia-Network/chia-dev-tools",
    },
)
