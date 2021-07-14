#!/usr/bin/env python

from setuptools import setup, find_packages

with open("README.md", "rt") as fh:
    long_description = fh.read()

dependencies = [
    "clvm_tools>=0.4.3",
    "clvm_rs>=0.1.1",
    "chia-blockchain>=1.2.0",
    "pytest",
    "pytest-asyncio",
    "pytimeparse",
]

dev_dependencies = []

setup(
    name="chialisp_dev_utility",
    version="0.0.8",
    packages=find_packages(),
    author="Quexington",
    entry_points={
        "console_scripts": [
            "chialisp = chialisp.cli:main"
        ],
    },
    author_email="quexington@gmail.com",
    setup_requires=["setuptools_scm"],
    install_requires=dependencies,
    url="https://github.com/Quexington",
    license="https://mit-license.org/",
    description="Chialisp development utility",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
        "Topic :: Security :: Cryptography",
    ],
    extras_require=dict(dev=dev_dependencies,),
    project_urls={
        "Bug Reports": "https://github.com/Quexington/chialisp_dev_utility",
        "Source": "https://github.com/Quexington/chialisp_dev_utility",
    },
)
