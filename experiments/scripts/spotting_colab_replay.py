"""Replay exact wheels without promoting transitive packages to direct requests."""
from pathlib import Path


def replay_commands(uv, work, directory, python_version, wheels, resolved, requirements):
    work, directory = Path(work).resolve(), Path(directory)
    if not directory.resolve().is_relative_to((work/'environments').resolve()):
        raise ValueError('replay target outside work environments')
    if (directory/'environment-seal.json').exists():
        raise ValueError('refuse clearing a sealed environment')
    venv = directory/'venv'
    if venv.is_symlink():
        raise ValueError('refuse replay into symlink venv')
    # A failed, unsealed replay may leave REQUESTED markers behind. Rebuild only
    # this ephemeral venv; never clear cached wheels, seals, models or outputs.
    create = list(uv)+['venv','--clear','--python',python_version,'--seed',venv]
    # Freeze constrains the graph but must not mark every transitive as requested.
    install = [venv/'bin/python','-m','pip','install','--no-index','--find-links',wheels,
               '--constraint',resolved,*requirements]
    return create, install
