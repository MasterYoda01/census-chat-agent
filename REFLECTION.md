# Reflection

## Development Process


### Key Architectural Decisions

**Two-tool function calling over single text-to-SQL:**

The central design choice was giving the LLM two tools: `run_sql_query` and `lookup_field_descriptions`. The alternative was putting all 8,164 field descriptions into the system prompt so the LLM always has complete knowledge.

I chose the two-tool approach because:
- The curated schema in the system prompt covers the ~15 most common topics (population, income, education, housing, race, poverty, employment, etc.) with specific column IDs. This handles 80%+ of questions instantly.
- The `lookup_field_descriptions` tool lets the LLM search the metadata table for anything not in the curated schema — so uncommon questions about, say, "kitchen facilities" or "vacancy status" still work. It searches across all 10 field description levels to find relevant column IDs.
- Sending 8K field descriptions on every API call would cost significantly more per question and add significant latency. The two-tool approach keeps common queries fast and cheap.

The tradeoff: uncommon questions take an extra tool call (and ~2-3 more seconds) to look up field descriptions first. I think this is the right call for a production system where cost and latency matter.

**Claude Sonnet over smaller models:**

Claude Sonnet 4.6 has strong text-to-SQL capabilities and native tool use (function calling) support. I considered smaller models to reduce cost but they produce worse SQL for complex multi-join queries — especially the CBG aggregation pattern which requires careful FIPS code joins and median handling.

**Direct Snowflake queries over materialized views or caching:**

I chose to query Snowflake directly rather than pre-computing aggregated tables (e.g., a state-level population table). This keeps the system flexible — it can answer any question the data supports, not just pre-computed ones. The tradeoff is slightly higher latency per query (~2-5 seconds for CBG-level aggregation across 242K rows), but Snowflake handles this well within the timeout limit.

**Streamlit over a custom frontend:**

Given the time constraint, Streamlit was the clear choice. It provides chat UI, session state, and deployment. A Next.js or React frontend would look more polished but would take 4-6 hours to build — time better spent on agent quality.

**Streaming progress updates over blocking:**

To prevent the UI from appearing frozen during multi-step queries (lookup + SQL execution + response generation), the pipeline yields status chunks as it works: "Thinking...", "Looking up fields...", "Running query 1...", "Analyzing results...". The final response is only rendered once complete to avoid broken Markdown mid-stream.

---

## What I Would Improve With More Time

1. **Query result caching.** Cache frequent queries (e.g., "population of California") in memory or Redis. The census data doesn't change, so cached results would be perfectly valid and would dramatically reduce latency and Snowflake costs.

2. **Evaluation framework.** Build a test suite of 50+ question/answer pairs with ground truth SQL and expected numeric answers. Run automated accuracy scoring on every code change. This is the single highest-leverage improvement.

3. **Schema-aware routing.** For very large schemas, use a two-step approach: first classify the question into a topic area, then load only the relevant table schemas. This would reduce token usage further.

4. **Connection pooling.** Currently each tool call creates a new Snowflake connection. A connection pool would reduce latency and be more resource-efficient.

5. **Better median aggregation.** The current system warns the LLM not to SUM medians, but a better approach would be to provide a weighted-average helper function or pre-compute state/county level medians.

6. **Visualization.** Return charts or tables alongside text answers. Streamlit supports `st.dataframe` and `st.bar_chart` natively — showing a population-by-state bar chart alongside the text answer would be much more useful.

7. **Rate limiting and authentication.** The deployed app has no authentication or rate limiting. A production deployment would need API key protection or basic auth, and rate limiting to prevent abuse of API credits.

8. **Observability.** Add structured logging, latency tracking per tool call, and error rate monitoring. In production, you'd want to know which queries are failing and why.

9. **2019 data support.** The system currently only uses 2020 tables. Adding 2019 support would let users compare years, but requires the LLM to understand which year's tables to query.

---

## Edge Cases & Failure Modes

### Identified and Addressed
- **Off-topic queries** — Guardrails reject clearly non-census questions (weather, stocks, sports, recipes, etc.) before they reach the LLM, saving API cost. The system prompt also instructs the LLM to decline topics not in the dataset (GDP, crime, etc.).
- **SQL injection** — Both guardrails (prompt injection) and tools (SQL statement validation) provide defense in depth.
- **SQL execution errors** — Errors are returned to the LLM as tool results, allowing one retry with the error context.
- **Empty result sets** — LLM is instructed to say "no data found" clearly.
- **Ambiguous queries** — LLM is instructed to ask for clarification (e.g., "What's the population?" → "Which state or county?").
- **Prompt injection** — Basic keyword detection catches common patterns.
- **State name format bug** — Agent was filtering `WHERE STATE = 'California'` instead of `'CA'`, returning zero rows. Fixed by adding an explicit note in the system prompt that the STATE column uses 2-letter abbreviations.
- **information_schema bypass** — Agent was querying `information_schema.columns` to discover column names, burning 4-6 tool calls before finding nothing. Fixed by adding an explicit critical rule forbidding `information_schema` use.
- **Metadata table direct query bypass** — Even after fixing `information_schema`, the agent bypassed `lookup_field_descriptions` and wrote custom SQL against `2020_METADATA_CBG_FIELD_DESCRIPTIONS` directly, consuming 8 tool calls. Fixed by adding a critical rule requiring the `lookup_field_descriptions` tool for all metadata searches.

### Identified but Not Fully Addressed
- **Median aggregation incorrectness** — The LLM knows not to SUM medians but may still attempt approximate weighted averages that aren't statistically rigorous. A proper fix would require pre-computing state/county medians from micro-data.
- **FIPS code join double-counting** — The FIPS codes table has one row per county. The system prompt warns about this and shows the DISTINCT pattern, but the LLM may not always use it.
- **Very complex multi-table queries** — Questions spanning multiple topics (e.g., "What's the correlation between income and education by state?") require joining multiple CBG tables. The LLM handles this reasonably well but may produce incorrect joins.
- **Rate limiting** — No protection against a user sending hundreds of queries quickly.
- **Concurrent users** — Each request creates a new Snowflake connection. Under high concurrency this could hit connection limits.
- **Sophisticated prompt injection** — The keyword-based guardrails catch basic patterns but a determined attacker could likely bypass them with obfuscation.

---

## Testing Approach

### What I Tested
- **Guardrails (18 tests):** Empty input, whitespace, length limits, prompt injection variations, unicode handling, off-topic query detection (weather, stocks, sports, recipes, etc.), and legitimate census questions passing through.
- **SQL safety (10 tests):** DROP/DELETE/INSERT/UPDATE/ALTER/TRUNCATE blocked, SELECT and WITH allowed, case-sensitivity bypass attempts, subquery and UNION handling.
- **Edge cases (18 tests):** SQL injection in messages, unicode, comment injection, mixed-case bypass attempts, off-topic guardrail coverage, and integration tests for ambiguous/off-topic/unanswerable queries — plus regression tests for real bugs found during testing (state abbreviation bug, information_schema bypass, metadata table direct query bypass, tool call exhaustion on unknown columns).

### Regression Tests from Real Bugs
Every significant bug found during live testing was converted into a permanent test case:
- `test_state_uses_abbreviation_not_full_name` — caught the full state name filter bug
- `test_does_not_query_information_schema` — caught the information_schema bypass
- `test_does_not_query_metadata_table_directly` — caught the metadata direct query bypass
- `test_unknown_column_resolves_in_few_calls` — caught tool call exhaustion on carpool queries

### What I Would Add
- **Ground truth evaluation:** 50+ questions with known correct numeric answers. For each: run the agent, extract the number from the response, compare to ground truth. Report accuracy percentage.
- **SQL correctness validation:** Parse generated SQL with a SQL parser, verify all referenced tables and columns actually exist in the schema.
- **Load testing:** Verify latency requirements under concurrent users.
- **LLM output stability:** Run the same question 10 times, check consistency of both SQL and final answer.
- **Cost tracking:** Monitor token usage per query to predict API costs at scale.

### Testing Tradeoffs
I focused on testing the layers I control (guardrails, SQL safety) rather than the LLM's output quality, because LLM behavior is non-deterministic and harder to test reliably. The integration tests marked `requires_api` verify end-to-end behavior but can't guarantee the LLM will always produce the exact same response. In production, I'd invest more heavily in the ground truth evaluation framework to catch quality regressions.

---

## How I Used AI Tools

- Used Claude to help with project scaffolding, architectural planning, and understanding the SafeGraph dataset schema.
- Used Claude to draft the system prompt, which I then refined based on actual query testing.
- Used Claude to generate test cases and identify edge cases I might have missed.
- Used Claude to help debug live failures — the state abbreviation bug, information_schema bypass, and metadata direct query issues were all identified and fixed by observing real agent behavior and iterating on the system prompt.
- All code was reviewed and understood before inclusion — I can explain every architectural decision and implementation detail.
