'''add metric definition json

Revision ID: a8c9d0e1f234
Revises: f1a2b3c4d5e6
Create Date: 2026-08-12 00:00:00.000000
'''

from collections.abc import Sequence
import re

import sqlalchemy as sa
from alembic import op

revision: str = 'a8c9d0e1f234'
down_revision: str | Sequence[str] | None = 'f1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FORMULA = re.compile(
    r'^(SUM|COUNT|AVG|MIN|MAX)\(\s*(?:DISTINCT\s+)?(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*|\*)\s*\)$',
    re.IGNORECASE,
)


def upgrade() -> None:
    '''Add JSON definitions and conservatively backfill simple legacy metrics.'''
    op.add_column('semantic_metrics', sa.Column('definition', sa.JSON(), nullable=True))
    op.add_column('metric_versions', sa.Column('definition', sa.JSON(), nullable=True))
    _backfill_metrics()


def downgrade() -> None:
    '''Remove JSON definitions without touching legacy text columns.'''
    op.drop_column('metric_versions', 'definition')
    op.drop_column('semantic_metrics', 'definition')


def _backfill_metrics() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    metrics = sa.Table('semantic_metrics', metadata, autoload_with=bind)
    tables = sa.Table('semantic_tables', metadata, autoload_with=bind)
    table_names = dict(bind.execute(sa.select(tables.c.id, tables.c.table_name)).all())
    rows = bind.execute(sa.select(metrics)).mappings().all()
    for row in rows:
        values = _legacy_definition(row, table_names)
        bind.execute(metrics.update().where(metrics.c.id == row['id']).values(**values))


def _legacy_definition(row: sa.RowMapping, table_names: dict[int, str]) -> dict[str, object]:
    formula = (row.get('formula') or '').strip()
    match = _FORMULA.fullmatch(formula)
    base_entity = table_names.get(row.get('base_entity_id'))
    if not match or not base_entity:
        return {'status': 'needs_review', 'definition': None}
    function = match.group(1).upper()
    if 'DISTINCT' in formula.upper():
        function = 'COUNT_DISTINCT'
    status = 'approved' if row.get('status') == 'approved' else 'pending_approval'
    definition = {
        'metric': {
            'name': row['name'],
            'formula': {'function': function, 'expression': match.group(2)},
            'base_entity': base_entity,
            'filters': [],
            'status': status,
            'confidence': None,
            'excluded_notes': '',
        }
    }
    return {'status': status, 'definition': definition}
