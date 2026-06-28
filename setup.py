# -*- coding: utf-8 -*-
"""setuptools shim — actual configuration lives in pyproject.toml."""
from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="capture-helper",
    version="0.0.1",
    description=(
        "Capture Helper — OBS-inspired (no GUI) capture, processing, and "
        "publishing for the AI Helpers stack. v0.0.1 ships device "
        "enumeration; the iter / mix / publish layers land in subsequent "
        "releases."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Warith HARCHAOUI",
    author_email="Warith HARCHAOUI <warithmetics@deraison.ai>",
    url="https://github.com/warith-harchaoui/capture-helper",
    packages=["capture_helper"],
    package_data={"": ["*"]},
    install_requires=[
        "os-helper @ git+https://github.com/warith-harchaoui/os-helper.git@v1.3.0",
    ],
    extras_require={
        "dev": ["pytest>=7"],
    },
    python_requires=">=3.10,<3.14",
)
