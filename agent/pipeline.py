"""
Main agent pipeline that orchestrates:
1. Guardrails check
2. Claude API call with tool use
3. Tool execution loop
4. Final response
"""

import json
import anthropic
from config.settings import settings
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.guardrails import validate_input


MODEL = "claude-sonnet-4-20250514"


def _get_client():
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def run_agent(conversation_history: list[dict], user_message: str) -> dict:
    """
    Process a user message through the full agent pipeline.

    Args:
        conversation_history: List of prior messages [{role, content}, ...]
        user_message: The new user message

    Returns:
        dict with:
            - "response": the agent's text response
            - "sql_queries": list of SQL queries that were executed (for transparency)
            - "error": error message if guardrails rejected the input
    """
    # Step 1: Guardrails
    is_valid, error_message = validate_input(user_message)
    if not is_valid:
        return {
            "response": error_message,
            "sql_queries": [],
            "error": True,
        }

    # Step 2: Build messages for Claude
    # Claude uses a separate system parameter, not a system message in the list
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
                # Build the assistant message content (may contain text + tool_use blocks)
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

                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each tool and collect results
                tool_results = []
                for block in tool_use_blocks:
                    tool_name = block.name
                    tool_args = block.input

                    # Track SQL queries for transparency
                    if tool_name == "run_sql_query" and "sql" in tool_args:
                        sql_queries.append({
                            "sql": tool_args["sql"],
                            "explanation": tool_args.get("explanation", ""),
                        })

                    # Execute the tool
                    tool_result = execute_tool(tool_name, tool_args)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result,
                    })

                    tool_call_count += 1

                # Add all tool results as a single user message
                messages.append({"role": "user", "content": tool_results})

            else:
                # No more tool calls — extract the final text response
                text_parts = []
                for block in response.content:
                    if block.type == "text":
                        text_parts.append(block.text)

                final_response = "\n".join(text_parts) if text_parts else (
                    "I wasn't able to generate a response. Please try rephrasing your question."
                )

                return {
                    "response": final_response,
                    "sql_queries": sql_queries,
                    "error": False,
                }

        # If we hit the tool call limit
        return {
            "response": (
                "I've reached the maximum number of queries for this question. "
                "Here's what I found so far based on the data retrieved. "
                "Could you try asking a more specific question?"
            ),
            "sql_queries": sql_queries,
            "error": False,
        }

    except anthropic.APIError as e:
        return {
            "response": f"I encountered an API error: {str(e)}. Please try again.",
            "sql_queries": sql_queries,
            "error": True,
        }
    except Exception as e:
        return {
            "response": (
                f"I encountered an error while processing your question: {str(e)}. "
                "Please try again or rephrase your question."
            ),
            "sql_queries": sql_queries,
            "error": True,
        }