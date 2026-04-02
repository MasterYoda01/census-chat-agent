"""
Main agent pipeline that orchestrates:
1. Guardrails check
2. Claude API call with tool use
3. Tool execution loop
4. Final streamed response
"""

import json
import anthropic
from config.settings import settings
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.guardrails import validate_input


MODEL = "claude-sonnet-4-6"


def _get_client():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def run_agent(conversation_history: list[dict], user_message: str) -> dict:
    """
    Non-streaming version (kept for tests and backward compatibility).
    """
    result = {"response": "", "sql_queries": [], "error": False}
    for chunk in run_agent_stream(conversation_history, user_message):
        if chunk["type"] == "error":
            return {"response": chunk["message"], "sql_queries": [], "error": True}
        elif chunk["type"] == "text_delta":
            result["response"] += chunk["content"]
        elif chunk["type"] == "sql_query":
            result["sql_queries"].append(chunk["query"])
        elif chunk["type"] == "done":
            result["sql_queries"] = chunk["sql_queries"]
    return result


def run_agent_stream(conversation_history: list[dict], user_message: str):
    """
    Process a user message through the agent pipeline, yielding chunks.

    Yields dicts with:
        {"type": "status", "message": "..."} — progress updates during tool use
        {"type": "sql_query", "query": {...}} — a SQL query that was executed
        {"type": "text_delta", "content": "..."} — streamed text token
        {"type": "done", "sql_queries": [...]} — final signal
        {"type": "error", "message": "..."} — error
    """
    # Step 1: Guardrails
    is_valid, error_message = validate_input(user_message)
    if not is_valid:
        yield {"type": "error", "message": error_message}
        return

    # Step 2: Build messages for Claude
    messages = list(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # Step 3: Tool use loop
    sql_queries = []
    tool_call_count = 0

    try:
        while tool_call_count < settings.MAX_TOOL_CALLS_PER_TURN:
            client = _get_client()
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                assistant_content = []
                tool_use_blocks = []

                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({
                            "type": "text",
                            "text": block.text,
                        })
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        tool_use_blocks.append(block)

                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool
                tool_results = []
                for block in tool_use_blocks:
                    tool_name = block.name
                    tool_args = block.input

                    if tool_name == "run_sql_query" and "sql" in tool_args:
                        query_info = {
                            "sql": tool_args["sql"],
                            "explanation": tool_args.get("explanation", ""),
                        }
                        sql_queries.append(query_info)
                        yield {"type": "sql_query", "query": query_info}
                        yield {"type": "status", "message": f"Running query {len(sql_queries)}..."}
                    elif tool_name == "lookup_field_descriptions":
                        yield {"type": "status", "message": f"Looking up fields for '{tool_args.get('search_term', '')}'..."}

                    tool_result = execute_tool(tool_name, tool_args)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result,
                    })
                    tool_call_count += 1

                messages.append({"role": "user", "content": tool_results})

                yield {"type": "status", "message": "Analyzing results..."}

            else:
                # Final response — stream it
                # We already have the full response, but we'll re-request with streaming
                # for the final turn to get token-by-token output
                final_text_parts = []
                for block in response.content:
                    if block.type == "text":
                        final_text_parts.append(block.text)

                if final_text_parts:
                    full_text = "\n".join(final_text_parts)
                    # Stream line-by-line to keep Markdown formatting intact
                    lines = full_text.split("\n")
                    for i, line in enumerate(lines):
                        suffix = "\n" if i < len(lines) - 1 else ""
                        yield {"type": "text_delta", "content": line + suffix}

                yield {"type": "done", "sql_queries": sql_queries}
                return

        yield {"type": "text_delta", "content": (
            "I've reached the maximum number of queries for this question. "
            "Could you try asking a more specific question?"
        )}
        yield {"type": "done", "sql_queries": sql_queries}

    except anthropic.APIError as e:
        yield {"type": "error", "message": f"API error: {str(e)}. Please try again."}
    except Exception as e:
        yield {"type": "error", "message": f"Error: {str(e)}. Please try again."}