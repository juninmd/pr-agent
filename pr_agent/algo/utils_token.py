from __future__ import annotations

from pr_agent.algo import MAX_TOKENS
from pr_agent.algo.token_handler import TokenEncoder
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger


def get_max_tokens(model):
    """
    Get the maximum number of tokens allowed for a model.
    logic:
    (1) If the model is in './pr_agent/algo/__init__.py', use the value from there.
    (2) else, the user needs to define explicitly 'config.custom_model_max_tokens'

    For both cases, we further limit the number of tokens to 'config.max_model_tokens' if it is set.
    This aims to improve the algorithmic quality, as the AI model degrades in performance when the input is too long.
    """
    settings = get_settings()
    if model in MAX_TOKENS:
        max_tokens_model = MAX_TOKENS[model]
    elif settings.config.custom_model_max_tokens > 0:
        max_tokens_model = settings.config.custom_model_max_tokens
    else:
        get_logger().error(f"Model {model} is not defined in MAX_TOKENS in ./pr_agent/algo/__init__.py and no custom_model_max_tokens is set")
        raise Exception(f"Ensure {model} is defined in MAX_TOKENS in ./pr_agent/algo/__init__.py or set a positive value for it in config.custom_model_max_tokens")

    if settings.config.max_model_tokens and settings.config.max_model_tokens > 0:
        max_tokens_model = min(settings.config.max_model_tokens, max_tokens_model)
    return max_tokens_model


def clip_tokens(text: str, max_tokens: int, add_three_dots=True, num_input_tokens=None, delete_last_line=False) -> str:
    """
    Clip the number of tokens in a string to a maximum number of tokens.

    This function limits text to a specified token count by calculating the approximate
    character-to-token ratio and truncating the text accordingly. A safety factor of 0.9
    (10% reduction) is applied to ensure the result stays within the token limit.

    Args:
        text (str): The string to clip. If empty or None, returns the input unchanged.
        max_tokens (int): The maximum number of tokens allowed in the string.
                         If negative, returns an empty string.
        add_three_dots (bool, optional): Whether to add "\\n...(truncated)" at the end
                                       of the clipped text to indicate truncation.
                                       Defaults to True.
        num_input_tokens (int, optional): Pre-computed number of tokens in the input text.
                                        If provided, skips token encoding step for efficiency.
                                        If None, tokens will be counted using TokenEncoder.
                                        Defaults to None.
        delete_last_line (bool, optional): Whether to remove the last line from the
                                         clipped content before adding truncation indicator.
                                         Useful for ensuring clean breaks at line boundaries.
                                         Defaults to False.

    Returns:
        str: The clipped string. Returns original text if:
             - Text is empty/None
             - Token count is within limit
             - An error occurs during processing

             Returns empty string if max_tokens <= 0.
    """
    if not text:
        return text

    try:
        if num_input_tokens is None:
            encoder = TokenEncoder.get_token_encoder()
            num_input_tokens = len(encoder.encode(text))
        if num_input_tokens <= max_tokens:
            return text
        if max_tokens < 0:
            return ""

        # calculate the number of characters to keep
        num_chars = len(text)
        chars_per_token = num_chars / num_input_tokens
        factor = 0.9  # reduce by 10% to be safe
        num_output_chars = int(factor * chars_per_token * max_tokens)

        # clip the text
        if num_output_chars > 0:
            clipped_text = text[:num_output_chars]
            if delete_last_line:
                clipped_text = clipped_text.rsplit('\n', 1)[0]
            if add_three_dots:
                clipped_text += "\n...(truncated)"
        else: # if the text is empty
            clipped_text =  ""

        return clipped_text
    except Exception as e:
        get_logger().warning(f"Failed to clip tokens: {e}")
        return text
