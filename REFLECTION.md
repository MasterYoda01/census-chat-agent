# Reflection

## Development Process

### Timeline
- **Hours 0-2:** Data exploration — set up Snowflake trial, installed marketplace dataset, ran SHOW TABLES, explored field descriptions and FIPS codes metadata, tested example queries to understand the CBG aggregation pattern.
- **Hours 2-8:** Core agent implementation — built the two-tool function calling architecture, wrote the curated schema system prompt, implemented Snowflake SQL execution with safety checks, and the pipeline orchestration loop.
- **Hours 8-10:** Chat UI with Streamlit — session state for multi-turn conversation, expandable SQL display, example questions.
- **Hours 10-12:** Guardrails, error handling, edge case hardening.
- **Hours 12-14:** Testing — unit tests for guardrails and SQL safety, edge case test suite.
- **Hours 14-16:** Deployment to Streamlit Community Cloud, end-to-end testing on deployed version.
- **Hours 16-18:** Reflection, README finalization, submission.

### Key Architectural Decisions

**Two-tool function calling over single text-to-SQL:**

The central design choice was giving the LLM two tools: `run_sql_query` and `lookup_field_descriptions`. The alternative was putting all 8,164 field descriptions into the system prompt so the LLM always has complete knowledge.

I chose the two-tool approach because:
- The curated schema in the system prompt covers the ~15 most common topics (population, income, education, housing, race, poverty, employment, etc.) with specific column IDs. This handles 80%+ of questions instantly.
- The `lookup_field_descriptions` tool lets the LLM search the metadata table for anything not in the curated schema — so uncommon questions about, say, "kitchen facilities" or "vacancy status" still work.
- Sending 8K field descriptions on every API call would cost ~$0.50-1.00+ per question and add significant latency. The two-tool approach keeps common queries fast and cheap.

The tradeoff: uncommon questions take an extra tool call (and ~2-3 more seconds) to look up field descriptions first. I think this is the right call for a production system where cost and latency matter.

**Direct Snowflake queries over materialized views or caching:**

I chose to query Snowflake directly rather than pre-computing aggregated tables (e.g., a state-level population table). This keeps the system flexible — it can answer any question the data supports, not just pre-computed ones. The tradeoff is slightly higher latency per query (~2-5 seconds for CBG-level aggregation across 242K rows), but Snowflake handles this well within the 60-second requirement.

**GPT-4o over Claude or smaller models:**

GPT-4o has strong text-to-SQL capabilities and native function calling support. I considered Claude (which I've used extensively) but OpenAI's function calling API is more mature and well-documented for this specific pattern. A smaller model like GPT-4o-mini could reduce cost but would likely produce worse SQL for complex multi-join queries.

**Streamlit over a custom frontend:**

Given the 24-hour constraint, Streamlit was the clear choice. It provides chat UI, session state, and deployment for free. A Next.js or React frontend would look more polished but would take 4-6 hours to build — time better spent on agent quality.

---

## What I Would Improve With More Time

1. **Query result caching.** Cache frequent queries (e.g., "population of California") in memory or Redis. The census data doesn't change, so cached results would be perfectly valid and would dramatically reduce latency and Snowflake costs.

2. **Evaluation framework.** Build a test suite of 50+ question/answer pairs with ground truth SQL and expected numeric answers. Run automated accuracy scoring on every code change. This is the single highest-leverage improvement.

3. **Schema-aware routing.** For very large schemas, use a two-step approach: first classify the question into a topic area, then load only the relevant table schemas. This would reduce token usage further.

4. **Streaming responses.** Stream the LLM's interpretation as it generates rather than waiting for the full response. This improves perceived performance significantly, especially for complex queries where the SQL execution takes a few seconds.

5. **Connection pooling.** Currently each tool call creates a new Snowflake connection. A connection pool would reduce latency and be more resource-efficient.

6. **Better median aggregation.** The current system warns the LLM not to SUM medians, but a better approach would be to provide a weighted-average helper function or pre-compute state/county level medians.

7. **Visualization.** Return charts or tables alongside text answers. Streamlit supports `st.dataframe` and `st.bar_chart` natively — showing a population-by-state bar chart alongside the text answer would be much more useful.

8. **Rate limiting and authentication.** The deployed app has no authentication or rate limiting. A production deployment would need API key protection or basic auth, and rate limiting to prevent abuse of OpenAI credits.

9. **Observability.** Add structured logging, latency tracking per tool call, and error rate monitoring. In production, you'd want to know which queries are failing and why.

10. **2019 data support.** The system currently only uses 2020 tables. Adding 2019 support would let users compare years, but requires the LLM to understand which year's tables to query.

---

## Edge Cases & Failure Modes

### Identified and Addressed
- **Off-topic queries** — Guardrails reject non-census questions; system prompt instructs LLM to decline topics not in the dataset (GDP, weather, etc.)
- **SQL injection** — Both guardrails (prompt injection) and tools (SQL statement validation) provide defense in depth
- **SQL execution errors** — Errors are returned to the LLM as tool results, allowing one retry with the error context
- **Empty result sets** — LLM is instructed to say "no data found" clearly
- **Ambiguous queries** — LLM is instructed to ask for clarification (e.g., "What's the population?" → "Which state or county?")
- **Prompt injection** — Basic keyword detection catches common patterns

### Identified but Not Fully Addressed
- **Median aggregation incorrectness** — The LLM knows not to SUM medians but may still attempt approximate weighted averages that aren't statistically rigorous. A proper fix would require pre-computing state/county medians from micro-data or using a different aggregation strategy.
- **FIPS code join double-counting** — The FIPS codes table has one row per county. When joining for state-level queries, this can cause double-counting if the JOIN isn't written carefully. The system prompt warns about this and shows the DISTINCT pattern, but the LLM may not always use it.
- **Very complex multi-table queries** — Questions spanning multiple topics (e.g., "What's the correlation between income and education by state?") require joining multiple CBG tables. The LLM handles this reasonably well but may produce incorrect joins.
- **Rate limiting** — No protection against a user sending hundreds of queries quickly, which would exhaust OpenAI API credits.
- **Concurrent users** — Each request creates a new Snowflake connection. Under high concurrency this could hit Snowflake connection limits.
- **Sophisticated prompt injection** — The keyword-based guardrails catch basic patterns but a determined attacker could likely bypass them with obfuscation.

---

## Testing Approach

### What I Tested
- **Guardrails (12 tests):** Empty input, whitespace, length limits, prompt injection variations, unicode handling, legitimate questions passing through.
- **SQL safety (10 tests):** DROP/DELETE/INSERT/UPDATE/ALTER/TRUNCATE blocked, SELECT and WITH allowed, case-sensitivity bypass attempts, subquery and UNION handling.
- **Edge cases (13 tests):** SQL injection in messages, unicode, comment injection, mixed-case bypass attempts, and integration tests for ambiguous/off-topic/unanswerable queries.

### What I Would Add
- **Ground truth evaluation:** 50+ questions with known correct numeric answers. For each: run the agent, extract the number from the response, compare to ground truth. Report accuracy percentage.
- **SQL correctness validation:** Parse generated SQL with a SQL parser, verify all referenced tables and columns actually exist in the schema.
- **Regression tests:** Every bug found during development becomes a permanent test case.
- **Load testing:** Verify the 60-second latency requirement under concurrent users using locust or similar.
- **LLM output stability:** Run the same question 10 times, check consistency of both SQL and final answer.
- **Cost tracking:** Monitor token usage per query to predict API costs at scale.

### Testing Tradeoffs
I focused on testing the layers I control (guardrails, SQL safety) rather than the LLM's output quality, because LLM behavior is non-deterministic and harder to test reliably. The integration tests marked `requires_api` verify end-to-end behavior but can't guarantee the LLM will always produce the exact same response. In production, I'd invest more heavily in the ground truth evaluation framework to catch quality regressions.

---

## How I Used AI Tools

- Used Claude to help with project scaffolding, architectural planning, and understanding the SafeGraph dataset schema.
- Used Claude to draft the system prompt, which I then refined based on actual query testing.
- Used Claude to generate test cases and identify edge cases I might have missed.
- All code was reviewed and understood before inclusion — I can explain every architectural decision and implementation detail.
