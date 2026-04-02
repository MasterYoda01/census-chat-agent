"""
Pre-LLM guardrails for input validation and off-topic detection.
"""


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
    message_lower = user_message.lower()
    for phrase in injection_phrases:
        if phrase in message_lower:
            return False, (
                "I'm designed to answer questions about US census and population data. "
                "How can I help you with demographic information?"
            )

    return True, None
