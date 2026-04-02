"""
Tools available to the LLM agent via function calling.

Tool 1: run_sql_query - Execute SQL against Snowflake and return results
Tool 2: lookup_field_descriptions - Search metadata to find column IDs for a topic
"""

import json
import snowflake.connector
from config.settings import settings


# ---------------------------------------------------------------------------
# Snowflake connection helper
# ---------------------------------------------------------------------------

def get_snowflake_connection():
    """Create a new Snowflake connection."""
    return snowflake.connector.connect(
        account=settings.SNOWFLAKE_ACCOUNT,
        user=settings.SNOWFLAKE_USER,
        password=settings.SNOWFLAKE_PASSWORD,
        warehouse=settings.SNOWFLAKE_WAREHOUSE,
        database=settings.SNOWFLAKE_DATABASE,
        schema=settings.SNOWFLAKE_SCHEMA,
    )


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic Claude format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "run_sql_query",
        "description": (
            "Execute a read-only SQL query against the US Census Snowflake database "
            "and return the results. Use this to answer questions about US population, "
            "demographics, income, housing, education, employment, and other census topics. "
            "All data is at the Census Block Group (CBG) level - you must aggregate "
            "(SUM, AVG, etc.) and join with the FIPS codes table to get state/county level answers. "
            'Table names must be double-quoted because they start with numbers (e.g., "2020_CBG_B01"). '
            "Only SELECT statements are allowed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A valid Snowflake SQL SELECT query. Must be read-only.",
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what this query does and why it answers the user's question.",
                },
            },
            "required": ["sql", "explanation"],
        },
    },
    {
        "name": "lookup_field_descriptions",
        "description": (
            "Search the census metadata table to find which column IDs correspond to a topic. "
            "Use this when you need to find the right column name for a demographic attribute "
            "that is not in your curated schema knowledge. "
            "For example, searching 'vacancy' will return column IDs like B25004e1, B25004e2 etc. "
            "with their full descriptions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": (
                        "The topic to search for (e.g., 'vacancy', 'disability', 'internet', "
                        "'bachelor degree field'). Will be matched against table titles and field descriptions."
                    ),
                },
            },
            "required": ["search_term"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution functions
# ---------------------------------------------------------------------------

def execute_sql_query(sql: str) -> str:
    """
    Execute a SQL query against Snowflake and return results as a JSON string.
    
    Returns:
        JSON string with either {"columns": [...], "rows": [...], "row_count": N}
        or {"error": "error message"} if the query fails.
    """
    # Safety check: only allow SELECT statements
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        return json.dumps({"error": "Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, DROP, or other modification statements."})

    # Block dangerous keywords
    dangerous_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE"]
    for keyword in dangerous_keywords:
        # Check for keyword as a standalone word (not part of a column name)
        if f" {keyword} " in f" {sql_stripped} " or sql_stripped.startswith(f"{keyword} "):
            return json.dumps({"error": f"Queries containing {keyword} are not allowed."})

    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()

        # Set query timeout
        cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {settings.SQL_TIMEOUT_SECONDS}")

        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(settings.MAX_SQL_ROWS_RETURNED)

        # Convert rows to list of lists (for JSON serialization)
        rows_serializable = []
        for row in rows:
            rows_serializable.append([
                str(val) if val is not None else None
                for val in row
            ])

        total_rows = cursor.rowcount

        result = {
            "columns": columns,
            "rows": rows_serializable,
            "row_count": total_rows,
            "note": f"Showing first {len(rows_serializable)} of {total_rows} rows" if total_rows > settings.MAX_SQL_ROWS_RETURNED else None,
        }

        cursor.close()
        conn.close()

        return json.dumps(result)

    except snowflake.connector.errors.ProgrammingError as e:
        return json.dumps({"error": f"SQL Error: {str(e)}"})
    except snowflake.connector.errors.DatabaseError as e:
        return json.dumps({"error": f"Database Error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})


def lookup_field_descriptions(search_term: str) -> str:
    """
    Search the field descriptions metadata table for columns matching a topic.
    
    Returns:
        JSON string with matching field descriptions.
    """
    sql = f"""
    SELECT 
        TABLE_ID,
        TABLE_NUMBER,
        TABLE_TITLE,
        FIELD_LEVEL_1,
        FIELD_LEVEL_2,
        FIELD_LEVEL_3,
        FIELD_LEVEL_4
    FROM "2020_METADATA_CBG_FIELD_DESCRIPTIONS"
    WHERE 
        UPPER(TABLE_TITLE) LIKE '%{search_term.upper().replace("'", "''")}%'
        OR UPPER(FIELD_LEVEL_2) LIKE '%{search_term.upper().replace("'", "''")}%'
        OR UPPER(FIELD_LEVEL_3) LIKE '%{search_term.upper().replace("'", "''")}%'
        OR UPPER(FIELD_LEVEL_4) LIKE '%{search_term.upper().replace("'", "''")}%'
    ORDER BY TABLE_ID
    LIMIT 50
    """

    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({col: (str(val) if val is not None else None) for col, val in zip(columns, row)})

        cursor.close()
        conn.close()

        if not results:
            return json.dumps({
                "message": f"No field descriptions found matching '{search_term}'. Try a different search term.",
                "results": [],
            })

        return json.dumps({
            "message": f"Found {len(results)} matching fields for '{search_term}'",
            "results": results,
        })

    except Exception as e:
        return json.dumps({"error": f"Error searching field descriptions: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Route a tool call to the right function and return the result as a string."""
    if tool_name == "run_sql_query":
        return execute_sql_query(tool_args.get("sql", ""))
    elif tool_name == "lookup_field_descriptions":
        return lookup_field_descriptions(tool_args.get("search_term", ""))
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})