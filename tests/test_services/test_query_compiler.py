'''Security guardrail tests for generated SQL.'''

import pytest

from src.services.query_compiler import validate_read_only


@pytest.mark.parametrize(
    'sql',
    [
        'INSERT INTO users(name) VALUES (1)',
        'UPDATE users SET name = 1',
        'DELETE FROM users',
        'DROP TABLE users',
        'ALTER TABLE users ADD x INT',
        'TRUNCATE TABLE users',
        'SELECT * INTO backup FROM users',
        'SELECT 1; DROP TABLE users',
        'WITH deleted AS (DELETE FROM users RETURNING *) SELECT * FROM deleted',
    ],
)
def test_validate_read_only_rejects_write_capable_sql(sql: str) -> None:
    with pytest.raises(ValueError):
        validate_read_only(sql)


def test_validate_read_only_accepts_single_select() -> None:
    assert validate_read_only('SELECT COUNT(*) FROM users LIMIT 100')
