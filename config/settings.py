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
    # Agent limits
    MAX_TOOL_CALLS_PER_TURN: int = 5
    MAX_SQL_ROWS_RETURNED: int = 100
    SQL_TIMEOUT_SECONDS: int = 30

    @property
    def SNOWFLAKE_ACCOUNT(self):
        return _get_secret("SNOWFLAKE_ACCOUNT")

    @property
    def SNOWFLAKE_USER(self):
        return _get_secret("SNOWFLAKE_USER")

    @property
    def SNOWFLAKE_PASSWORD(self):
        return _get_secret("SNOWFLAKE_PASSWORD")

    @property
    def SNOWFLAKE_WAREHOUSE(self):
        return _get_secret("SNOWFLAKE_WAREHOUSE")

    @property
    def SNOWFLAKE_DATABASE(self):
        return _get_secret("SNOWFLAKE_DATABASE", "US_OPEN_CENSUS_DATA__NEIGHBORHOOD_INSIGHTS__FREE_DATASET")

    @property
    def SNOWFLAKE_SCHEMA(self):
        return _get_secret("SNOWFLAKE_SCHEMA", "PUBLIC")

    @property
    def ANTHROPIC_API_KEY(self):
        return _get_secret("ANTHROPIC_API_KEY")


settings = Settings()