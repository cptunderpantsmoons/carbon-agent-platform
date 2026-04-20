"""Automatic temperature detection based on task analysis.

Analyzes user messages to determine the optimal temperature setting
based on DeepSeek's recommendations and general LLM best practices.
"""
import re
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class TaskType(Enum):
    """Task types recognized by the temperature detector."""
    CODING = "coding"
    MATH = "math"
    DATA_ANALYSIS = "data_analysis"
    TRANSLATION = "translation"
    CREATIVE_WRITING = "creative_writing"
    GENERAL_CONVERSATION = "general_conversation"
    QUESTION_ANSWERING = "question_answering"
    SUMMARIZATION = "summarization"


# Temperature recommendations (DeepSeek guidelines)
TEMPERATURE_MAP = {
    TaskType.CODING: 0.0,
    TaskType.MATH: 0.0,
    TaskType.DATA_ANALYSIS: 1.0,
    TaskType.TRANSLATION: 1.3,
    TaskType.CREATIVE_WRITING: 1.5,
    TaskType.GENERAL_CONVERSATION: 1.3,
    TaskType.QUESTION_ANSWERING: 1.0,
    TaskType.SUMMARIZATION: 0.7,
}

# Keyword patterns for task detection
TASK_PATTERNS = {
    TaskType.CODING: [
        r'\b(write|create|implement|code|function|class|method|algorithm)\b.*\b(python|java|javascript|c\+\+|rust|go|ruby)\b',
        r'\b(debug|fix|error|bug|exception|traceback)\b.*\b(code|program|script)\b',
        r'\b(refactor|optimize|improve)\b.*\b(code|performance|efficiency)\b',
        r'\b(api|endpoint|route|server|database|query)\b',
        r'\b(sort|search|parse|validate|serialize)\b',
        r'```[\w]+\n',  # Code blocks
        r'def \w+\(',  # Python function definition
        r'function \w+\(',  # JavaScript function
    ],
    TaskType.MATH: [
        r'\b(solve|calculate|compute|evaluate)\b.*\b(equation|formula|integral|derivative)\b',
        r'\b(mathematics|calculus|algebra|geometry|trigonometry|statistics)\b',
        r'\b(prove|theorem|lemma|corollary)\b',
        r'[+\-*/^]=?\s*\d+',  # Mathematical expressions
        r'\b(sqrt|sin|cos|tan|log|ln|exp|pi)\b',
        r'\b(sum|product|limit|series|matrix)\b',
    ],
    TaskType.DATA_ANALYSIS: [
        r'\b(analyze|analysis|process|clean|transform)\b.*\b(data|dataset|csv|excel)\b',
        r'\b(statistics|correlation|regression|distribution|variance)\b',
        r'\b(visualization|chart|graph|plot|dashboard)\b',
        r'\b(pandas|numpy|matplotlib|seaborn|tensorflow)\b',
        r'\b(mean|median|mode|standard deviation|percentile)\b',
        r'\b(filter|group|aggregate|pivot|merge)\b.*\b(data)\b',
    ],
    TaskType.TRANSLATION: [
        r'\b(translate|translation|convert)\b.*\b(language|english|chinese|spanish|french|german|japanese)\b',
        r'\b(in \w+|to \w+|from \w+)\b.*\b(language)\b',
        r'^(translate|translation):',
    ],
    TaskType.CREATIVE_WRITING: [
        r'\b(write|create|compose|draft)\b.*\b(poem|story|novel|essay|article|blog)\b',
        r'\b(creative|imaginative|artistic|literary|fictional)\b',
        r'\b(storytelling|narrative|character|plot|dialogue)\b',
        r'\b(poetry|rhyme|verse|stanza|metaphor|simile)\b',
        r'\b(imagine|envision|picture|dream)\b',
    ],
    TaskType.SUMMARIZATION: [
        r'\b(summarize|summary|condense|brief)\b',
        r'\b(key points|main ideas|highlights|overview)\b',
        r'\b(tl;dr|too long|in short|to summarize)\b',
        r'\b(extract|outline|bullet points)\b.*\b(summary)\b',
    ],
}


def detect_task_type(message: str) -> TaskType:
    """Detect the task type from a user message.
    
    Analyzes the message content using pattern matching to determine
    the most likely task type. Falls back to general conversation if
    no specific pattern matches.
    
    Args:
        message: The user's message text.
        
    Returns:
        Detected TaskType enum value.
    """
    message_lower = message.lower()
    
    # Check each task type's patterns
    for task_type, patterns in TASK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                logger.debug(
                    "task_type_detected",
                    task_type=task_type.value,
                    pattern=pattern,
                )
                return task_type
    
    # Default to general conversation
    return TaskType.GENERAL_CONVERSATION


def get_optimal_temperature(
    message: str,
    task_type: Optional[TaskType] = None,
    provider: str = "deepseek",
) -> float:
    """Get the optimal temperature for a given message.
    
    Automatically detects the task type and returns the recommended
    temperature based on provider-specific guidelines.
    
    Args:
        message: The user's message text.
        task_type: Optional pre-detected task type. If None, will be detected.
        provider: LLM provider name (affects temperature recommendations).
        
    Returns:
        Optimal temperature value (0.0-1.5).
    """
    # Detect task type if not provided
    if task_type is None:
        task_type = detect_task_type(message)
    
    # Get base temperature from map
    temperature = TEMPERATURE_MAP.get(task_type, 1.0)
    
    # Provider-specific adjustments
    if provider == "openai":
        # OpenAI generally works well with slightly lower temperatures
        temperature = max(0.0, temperature - 0.2)
    elif provider == "anthropic":
        # Claude has stricter temperature limits (0.0-1.0)
        temperature = min(1.0, temperature)
    elif provider == "featherless":
        # Open-source models may need slight adjustment
        temperature = max(0.5, min(1.2, temperature))
    # DeepSeek uses the base temperature as-is
    
    logger.info(
        "temperature_auto_selected",
        task_type=task_type.value,
        temperature=temperature,
        provider=provider,
    )
    
    return temperature


def detect_and_apply_temperature(
    messages: list[dict],
    current_temperature: Optional[float] = None,
    provider: str = "deepseek",
) -> float:
    """Detect task type from conversation and return optimal temperature.
    
    Analyzes the full conversation context (not just the last message)
    to make a more informed temperature decision.
    
    Args:
        messages: List of conversation messages.
        current_temperature: User-specified temperature (if any).
        provider: LLM provider name.
        
    Returns:
        Optimal temperature value.
    """
    # If user explicitly set temperature, respect it
    if current_temperature is not None and current_temperature >= 0:
        logger.info(
            "temperature_user_specified",
            temperature=current_temperature,
        )
        return current_temperature
    
    # Analyze conversation context
    # Use the last user message for task detection
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    
    if not user_messages:
        logger.warning("no_user_messages_found", using_default_temp=1.0)
        return 1.0
    
    # Get the most recent user message
    last_user_message = user_messages[-1].get("content", "")
    
    # Combine with system prompt context if available
    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    system_context = " ".join([msg.get("content", "") for msg in system_messages])
    
    # Enhanced detection with context
    full_context = f"{system_context} {last_user_message}" if system_context else last_user_message
    
    # Detect task type
    task_type = detect_task_type(full_context)
    
    # Get optimal temperature
    temperature = get_optimal_temperature(full_context, task_type, provider)
    
    logger.info(
        "temperature_automatically_selected",
        task_type=task_type.value,
        temperature=temperature,
        message_preview=last_user_message[:100],
    )
    
    return temperature


def get_task_description(task_type: TaskType) -> str:
    """Get a human-readable description of the task type.
    
    Args:
        task_type: TaskType enum value.
        
    Returns:
        Human-readable task description.
    """
    descriptions = {
        TaskType.CODING: "Code generation or debugging",
        TaskType.MATH: "Mathematical calculation or proof",
        TaskType.DATA_ANALYSIS: "Data analysis or processing",
        TaskType.TRANSLATION: "Language translation",
        TaskType.CREATIVE_WRITING: "Creative writing or content generation",
        TaskType.GENERAL_CONVERSATION: "General conversation",
        TaskType.QUESTION_ANSWERING: "Question answering",
        TaskType.SUMMARIZATION: "Text summarization",
    }
    return descriptions.get(task_type, "Unknown task")
