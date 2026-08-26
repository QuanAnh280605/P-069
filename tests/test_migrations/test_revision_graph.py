"""Revision graph integrity tests for Alembic migrations.

These tests guard against the production deploy defect where two migration
files declared the same revision ID and the revision graph forked into
multiple heads. The graph must always resolve to exactly one head with
unique revision identifiers.
"""

import importlib.util
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_DUPLICATE_MODULE_PREFIX = "_rev_graph_"


def _project_root() -> Path:
    """Return the repository root containing alembic.ini."""
    return Path(__file__).resolve().parents[2]


def _script_directory() -> ScriptDirectory:
    """Build an Alembic ScriptDirectory from the project config."""
    config = Config(str(_project_root() / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def _import_version_module(path: Path):
    """Import a single migration file and return its module object."""
    spec = importlib.util.spec_from_file_location(f"{_DUPLICATE_MODULE_PREFIX}{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _collect_revision_ids():
    """Return a list of (revision_id, filename) declared by every version file."""
    versions_dir = _project_root() / "alembic" / "versions"
    collected = []
    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = _import_version_module(path)
        revision = getattr(module, "revision", None)
        if revision is None:
            continue
        collected.append((revision, path.name))
    return collected


def test_all_revision_ids_unique():
    """No two migration files may declare the same revision identifier."""
    collected = _collect_revision_ids()
    seen: dict[str, str] = {}
    duplicates = []
    for revision_id, filename in collected:
        if revision_id in seen:
            duplicates.append((revision_id, seen[revision_id], filename))
        else:
            seen[revision_id] = filename
    assert not duplicates, f"Duplicate revision IDs detected: {duplicates}"


def test_exactly_one_head():
    """The revision graph must converge to exactly one head."""
    script_directory = _script_directory()
    heads = script_directory.get_heads()
    assert len(heads) == 1, f"Expected exactly one head, found {len(heads)}: {heads}"
