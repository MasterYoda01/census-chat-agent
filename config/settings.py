import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """
    Get a secret from environment variables or Streamlit secrets.
    Streamlit Cloud stores secrets in st.secrets, which are also
    injected as environment variables. This function checks both
    to work locally (.env) and in Streamlit Cloud.
    """
    # First check env vars (works for both .env locally and Streamlit Cloud)
    value = os.getenv(key, "")
    if value:
        return value

    # Fallback: try Streamlit secrets directly
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


class Settings:
    SNOWFLAKE_ACCOUNT: str = _get_secret("SNOWFLAKE_ACCOUNT")
    SNOWFLAKE_USER: str = _get_secret("SNOWFLAKE_USER")
    SNOWFLAKE_PASSWORD: str = _get_secret("SNOWFLAKE_PASSWORD")
    SNOWFLAKE_WAREHOUSE: str = _get_secret("SNOWFLAKE_WAREHOUSE")
    SNOWFLAKE_DATABASE: str = _get_secret(
        "SNOWFLAKE_DATABASE",
        "US_OPEN_CENSUS_DATA__NEIGHBORHOOD_INSIGHTS__FREE_DATASET",
    )
    SNOWFLAKE_SCHEMA: str = _get_secret("SNOWFLAKE_SCHEMA", "PUBLIC")
    ANTHROPIC_API_KEY: str = _get_secret("ANTHROPIC_API_KEY")

    # Agent limits
    MAX_TOOL_CALLS_PER_TURN: int = 5
    MAX_SQL_ROWS_RETURNED: int = 100
    SQL_TIMEOUT_SECONDS: int = 30


settings = Settings()