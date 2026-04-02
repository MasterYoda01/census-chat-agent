"""
Pre-LLM guardrails for input validation and off-topic detection.
"""

# Topics clearly outside the census dataset — caught before hitting the LLM
_OFF_TOPIC_PHRASES = [
    "weather", "forecast", "temperature", "climate",
    "stock", "share price", "nasdaq", "s&p", "crypto", "bitcoin",
    "sports", "nfl", "nba", "mlb", "soccer", "football score",
    "recipe", "cook", "restaurant",
    "movie", "film", "tv show", "netflix",
    "write me a", "write a poem", "tell me a joke",
    "translate", "what time is it",
]

_OFF_TOPIC_RESPONSE = (
    "I can only answer questions about US census and demographic data "
    "(population, income, housing, education, employment, etc.). "
    "How can I help you with that?"
)


def validate_input(user_message: str) -> tuple[bool, str | None]:
    """
    Validate user input before sending to the LLM.

    Returns:
        (is_valid, error_message) - if is_valid is False, error_message explains why.
    """
    # Empty or whitespace-only input
    if not user_message or not user_message.strip():
        return False, "Please enter a question about US census or population data."

    # Too short to be meaningful
    if len(user_message.strip()) < 2:
        return False, "Your message is too short. Please ask a complete question about US census data."

    # Too long (potential prompt injection or abuse)
    if len(user_message) > 2000:
        return False, "Your message is too long. Please keep your question under 2000 characters."

    message_lower = user_message.lower()

    # Check for prompt injection attempts
    injection_phrases = [
        "ignore your instructions",
        "ignore all previous",
        "disregard your",
        "forget your instructions",
        "you are now",
        "new instructions:",
        "system prompt:",
        "override your",
        "act as if",
        "pretend you are",
    ]
    for phrase in injection_phrases:
        if phrase in message_lower:
            return False, (
                "I'm designed to answer questions about US census and population data. "
                "How can I help you with demographic information?"
            )

    # Catch obviously off-topic queries before they reach the LLM
    for phrase in _OFF_TOPIC_PHRASES:
        if phrase in message_lower:
            return False, _OFF_TOPIC_RESPONSE

    return True, None
