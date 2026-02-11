from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import html
import json
import os
import re
import sys
import textwrap
import time
import traceback
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any, List, Tuple

import html2text
import requests
import yaml
from starlette_context import context

from pr_agent.algo import MAX_TOKENS
from pr_agent.algo.language_handler import set_file_languages
from pr_agent.algo.token_handler import TokenEncoder
from pr_agent.algo.types import FilePatchInfo
from pr_agent.algo.utils_markdown import (convert_to_markdown_v2,
                                          emphasize_header, format_todo_item,
                                          format_todo_items, is_value_no,
                                          parse_code_suggestion,
                                          process_can_be_split,
                                          ticket_markdown_logic)
from pr_agent.algo.utils_serialization import (fix_json_escape_char, load_yaml,
                                               try_fix_json, try_fix_yaml)
from pr_agent.config_loader import get_settings, global_settings
from pr_agent.log import get_logger

# Re-exporting from new modules
from pr_agent.algo.utils_token import get_max_tokens, clip_tokens
from pr_agent.algo.utils_diff import load_large_diff, find_line_number_of_relevant_line_in_file
from pr_agent.algo.utils_github import get_rate_limit_status, validate_rate_limit_github, validate_and_await_rate_limit, github_action_output
from pr_agent.algo.utils_text import (unique_strings, convert_str_to_datetime, update_settings_from_args,
                                      show_relevant_configurations, set_pr_string, string_to_uniform_number,
                                      process_description, get_version, replace_code_tags)


def get_model(model_type: str = "model_weak") -> str:
    if model_type == "model_weak" and get_settings().get("config.model_weak"):
        return get_settings().config.model_weak
    elif model_type == "model_reasoning" and get_settings().get("config.model_reasoning"):
        return get_settings().config.model_reasoning
    return get_settings().config.model


from pr_agent.algo.types import (ModelType, PRDescriptionHeader, PRReviewHeader,
                                 Range, ReasoningEffort, TodoItem)


def get_setting(key: str) -> Any:
    try:
        key = key.upper()
        return context.get("settings", global_settings).get(key, global_settings.get(key, None))
    except Exception:
        return global_settings.get(key, None)


def set_custom_labels(variables, git_provider=None):
    if not get_settings().config.enable_custom_labels:
        return

    labels = get_settings().get('custom_labels', {})
    if not labels:
        # set default labels
        labels = ['Bug fix', 'Tests', 'Bug fix with tests', 'Enhancement', 'Documentation', 'Other']
        labels_list = "\n      - ".join(labels) if labels else ""
        labels_list = f"      - {labels_list}" if labels_list else ""
        variables["custom_labels"] = labels_list
        return

    # Set custom labels
    variables["custom_labels_class"] = "class Label(str, Enum):"
    counter = 0
    labels_minimal_to_labels_dict = {}
    for k, v in labels.items():
        description = "'" + v['description'].strip('\n').replace('\n', '\\n') + "'"
        # variables["custom_labels_class"] += f"\n    {k.lower().replace(' ', '_')} = '{k}' # {description}"
        variables["custom_labels_class"] += f"\n    {k.lower().replace(' ', '_')} = {description}"
        labels_minimal_to_labels_dict[k.lower().replace(' ', '_')] = k
        counter += 1
    variables["labels_minimal_to_labels_dict"] = labels_minimal_to_labels_dict

def get_user_labels(current_labels: List[str] = None):
    """
    Only keep labels that has been added by the user
    """
    try:
        enable_custom_labels = get_settings().config.get('enable_custom_labels', False)
        custom_labels = get_settings().get('custom_labels', [])
        if current_labels is None:
            current_labels = []
        user_labels = []
        for label in current_labels:
            if label.lower() in ['bug fix', 'tests', 'enhancement', 'documentation', 'other']:
                continue
            if enable_custom_labels:
                if label in custom_labels:
                    continue
            user_labels.append(label)
        if user_labels:
            get_logger().debug(f"Keeping user labels: {user_labels}")
    except Exception as e:
        get_logger().exception(f"Failed to get user labels: {e}")
        return current_labels
    return user_labels
