#!/usr/bin/env python3
"""
Allow the CLI package to be run as a module: python -m cli
"""

from cli.commands.cli import main

if __name__ == "__main__":
    main()