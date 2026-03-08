"""
Command registration hub — imports all command modules and wires their
parsers into the argparse subparser collection.

Each module defines ``setup(sub, registry)`` which adds its subparsers
and registers handler functions with the registry.
"""

from . import (
    analysis_cmds,
    auth_cmds,
    connect_cmds,
    deploy_cmds,
    distribute_cmds,
    project_cmds,
    run_cmds,
    scaffold_cmds,
    vault_cmds,
)

_ALL_MODULES = [
    scaffold_cmds,
    analysis_cmds,
    run_cmds,
    deploy_cmds,
    connect_cmds,
    project_cmds,
    distribute_cmds,
    auth_cmds,
    vault_cmds,
]


def setup_all(sub, registry):
    """Register every command group's parsers and handlers."""
    for mod in _ALL_MODULES:
        mod.setup(sub, registry)
