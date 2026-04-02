"""Tests for tool execution and SQL safety."""

import json
from agent.tools import execute_sql_query, execute_tool


class TestSQLSafety:
    """Test that dangerous SQL is blocked."""

    def test_block_drop_table(self):
        result = json.loads(execute_sql_query("DROP TABLE users"))
        assert "error" in result
        assert "DROP" in result["error"]

    def test_block_delete(self):
        result = json.loads(execute_sql_query("DELETE FROM users WHERE 1=1"))
        assert "error" in result

    def test_block_insert(self):
        result = json.loads(execute_sql_query("INSERT INTO users VALUES (1, 'test')"))
        assert "error" in result

    def test_block_update(self):
        result = json.loads(execute_sql_query("UPDATE users SET name = 'hacked'"))
        assert "error" in result

    def test_block_alter(self):
        result = json.loads(execute_sql_query("ALTER TABLE users ADD COLUMN x INT"))
        assert "error" in result

    def test_block_truncate(self):
        result = json.loads(execute_sql_query("TRUNCATE TABLE users"))
        assert "error" in result

    def test_allow_select(self):
        # This will fail to connect (no creds in test) but should NOT be blocked by safety check
        result = json.loads(execute_sql_query('SELECT 1 as test'))
        # Should either succeed or fail with connection error, NOT a safety error
        if "error" in result:
            assert "Only SELECT" not in result["error"]
            assert "DROP" not in result["error"]

    def test_allow_with_cte(self):
        result = json.loads(execute_sql_query('WITH cte AS (SELECT 1) SELECT * FROM cte'))
        if "error" in result:
            assert "Only SELECT" not in result["error"]


class TestToolDispatch:
    """Test the tool dispatch function."""

    def test_unknown_tool(self):
        result = json.loads(execute_tool("nonexistent_tool", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_sql_tool_dispatch(self):
        result = json.loads(execute_tool("run_sql_query", {"sql": "DROP TABLE x"}))
        assert "error" in result
        assert "DROP" in result["error"]
