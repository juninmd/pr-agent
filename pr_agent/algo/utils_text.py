from __future__ import annotations

import hashlib
import html
import re
import sys
import os
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import List, Tuple

import html2text
import yaml

from pr_agent.algo.types import PRDescriptionHeader
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger


def unique_strings(input_list: List[str]) -> List[str]:
    if not input_list or not isinstance(input_list, list):
        return input_list
    seen = set()
    unique_list = []
    for item in input_list:
        if item not in seen:
            unique_list.append(item)
            seen.add(item)
    return unique_list


def convert_str_to_datetime(date_str):
    """
    Convert a string representation of a date and time into a datetime object.

    Args:
        date_str (str): A string representation of a date and time in the format '%a, %d %b %Y %H:%M:%S %Z'

    Returns:
        datetime: A datetime object representing the input date and time.

    Example:
        >>> convert_str_to_datetime('Mon, 01 Jan 2022 12:00:00 UTC')
        datetime.datetime(2022, 1, 1, 12, 0, 0)
    """
    datetime_format = '%a, %d %b %Y %H:%M:%S %Z'
    return datetime.strptime(date_str, datetime_format)


def update_settings_from_args(args: List[str]) -> List[str]:
    """
    Update the settings of the Dynaconf object based on the arguments passed to the function.

    Args:
        args: A list of arguments passed to the function.
        Example args: ['--pr_code_suggestions.extra_instructions="be funny',
                  '--pr_code_suggestions.num_code_suggestions=3']

    Returns:
        None

    Raises:
        ValueError: If the argument is not in the correct format.

    """
    other_args = []
    if args:
        for arg in args:
            arg = arg.strip()
            if arg.startswith('--'):
                arg = arg.strip('-').strip()
                vals = arg.split('=', 1)
                if len(vals) != 2:
                    if len(vals) > 2:  # --extended is a valid argument
                        get_logger().error(f'Invalid argument format: {arg}')
                    other_args.append(arg)
                    continue
                key, value = _fix_key_value(*vals)
                get_settings().set(key, value)
                get_logger().info(f'Updated setting {key} to: "{value}"')
            else:
                other_args.append(arg)
    return other_args


def _fix_key_value(key: str, value: str):
    key = key.strip().upper()
    value = value.strip()
    try:
        value = yaml.safe_load(value)
    except Exception as e:
        get_logger().debug(f"Failed to parse YAML for config override {key}={value}", exc_info=e)
    return key, value


def show_relevant_configurations(relevant_section: str) -> str:
    skip_keys = ['ai_disclaimer', 'ai_disclaimer_title', 'ANALYTICS_FOLDER', 'secret_provider', "skip_keys", "app_id", "redirect",
                      'trial_prefix_message', 'no_eligible_message', 'identity_provider', 'ALLOWED_REPOS','APP_NAME']
    extra_skip_keys = get_settings().config.get('config.skip_keys', [])
    if extra_skip_keys:
        skip_keys.extend(extra_skip_keys)

    markdown_text = ""
    markdown_text += "\n<hr>\n<details> <summary><strong>🛠️ Relevant configurations:</strong></summary> \n\n"
    markdown_text +="<br>These are the relevant [configurations](https://github.com/Codium-ai/pr-agent/blob/main/pr_agent/settings/configuration.toml) for this tool:\n\n"
    markdown_text += f"**[config**]\n```yaml\n\n"
    for key, value in get_settings().config.items():
        if key in skip_keys:
            continue
        markdown_text += f"{key}: {value}\n"
    markdown_text += "\n```\n"
    markdown_text += f"\n**[{relevant_section}]**\n```yaml\n\n"
    for key, value in get_settings().get(relevant_section, {}).items():
        if key in skip_keys:
            continue
        markdown_text += f"{key}: {value}\n"
    markdown_text += "\n```"
    markdown_text += "\n</details>\n"
    return markdown_text


def set_pr_string(repo_name, pr_number):
    return f"{repo_name}#{pr_number}"


def string_to_uniform_number(s: str) -> float:
    """
    Convert a string to a uniform number in the range [0, 1].
    The uniform distribution is achieved by the nature of the SHA-256 hash function, which produces a uniformly distributed hash value over its output space.
    """
    # Generate a hash of the string
    hash_object = hashlib.sha256(s.encode())
    # Convert the hash to an integer
    hash_int = int(hash_object.hexdigest(), 16)
    # Normalize the integer to the range [0, 1]
    max_hash_int = 2 ** 256 - 1
    uniform_number = float(hash_int) / max_hash_int
    return uniform_number


def process_description(description_full: str) -> Tuple[str, List]:
    if not description_full:
        return "", []

    # description_split = description_full.split(PRDescriptionHeader.FILE_WALKTHROUGH.value)
    if PRDescriptionHeader.FILE_WALKTHROUGH.value in description_full:
        try:
            # FILE_WALKTHROUGH are presented in a collapsible section in the description
            regex_pattern = r'<details.*?>\s*<summary>\s*<h3>\s*' + re.escape(PRDescriptionHeader.FILE_WALKTHROUGH.value) + r'\s*</h3>\s*</summary>'
            description_split = re.split(regex_pattern, description_full, maxsplit=1, flags=re.DOTALL)

            # If the regex pattern is not found, fallback to the previous method
            if len(description_split) == 1:
                get_logger().debug("Could not find regex pattern for file walkthrough, falling back to simple split")
                description_split = description_full.split(PRDescriptionHeader.FILE_WALKTHROUGH.value, 1)
        except Exception as e:
            get_logger().warning(f"Failed to split description using regex, falling back to simple split: {e}")
            description_split = description_full.split(PRDescriptionHeader.FILE_WALKTHROUGH.value, 1)

        if len(description_split) < 2:
            get_logger().error("Failed to split description into base and changes walkthrough", artifact={'description': description_full})
            return description_full.strip(), []

        base_description_str = description_split[0].strip()
        changes_walkthrough_str = ""
        files = []
        if len(description_split) > 1:
            changes_walkthrough_str = description_split[1]
        else:
            get_logger().debug("No changes walkthrough found")
    else:
        base_description_str = description_full.strip()
        return base_description_str, []

    try:
        if changes_walkthrough_str:
            # get the end of the table
            if '</table>\n\n___' in changes_walkthrough_str:
                end = changes_walkthrough_str.index("</table>\n\n___")
            elif '\n___' in changes_walkthrough_str:
                end = changes_walkthrough_str.index("\n___")
            else:
                end = len(changes_walkthrough_str)
            changes_walkthrough_str = changes_walkthrough_str[:end]

            h = html2text.HTML2Text()
            h.body_width = 0  # Disable line wrapping

            # find all the files
            pattern = r'<tr>\s*<td>\s*(<details>\s*<summary>(.*?)</summary>(.*?)</details>)\s*</td>'
            files_found = re.findall(pattern, changes_walkthrough_str, re.DOTALL)
            for file_data in files_found:
                try:
                    if isinstance(file_data, tuple):
                        file_data = file_data[0]
                    pattern = r'<details>\s*<summary><strong>(.*?)</strong>\s*<dd><code>(.*?)</code>.*?</summary>\s*<hr>\s*(.*?)\s*(?:<li>|•)(.*?)</details>'
                    res = re.search(pattern, file_data, re.DOTALL)
                    if not res or res.lastindex != 4:
                        pattern_back = r'<details>\s*<summary><strong>(.*?)</strong><dd><code>(.*?)</code>.*?</summary>\s*<hr>\s*(.*?)\n\n\s*(.*?)</details>'
                        res = re.search(pattern_back, file_data, re.DOTALL)
                    if not res or res.lastindex != 4:
                        pattern_back = r'<details>\s*<summary><strong>(.*?)</strong>\s*<dd><code>(.*?)</code>.*?</summary>\s*<hr>\s*(.*?)\s*-\s*(.*?)\s*</details>' # looking for hypen ('- ')
                        res = re.search(pattern_back, file_data, re.DOTALL)
                    if res and res.lastindex == 4:
                        short_filename = res.group(1).strip()
                        short_summary = res.group(2).strip()
                        long_filename = res.group(3).strip()
                        if long_filename.endswith('<ul>'):
                            long_filename = long_filename[:-4].strip()
                        long_summary =  res.group(4).strip()
                        long_summary = long_summary.replace('<br> *', '\n*').replace('<br>','').replace('\n','<br>')
                        long_summary = h.handle(long_summary).strip()
                        if long_summary.startswith('\\-'):
                            long_summary = "* " + long_summary[2:]
                        elif not long_summary.startswith('*'):
                            long_summary = f"* {long_summary}"

                        files.append({
                            'short_file_name': short_filename,
                            'full_file_name': long_filename,
                            'short_summary': short_summary,
                            'long_summary': long_summary
                        })
                    else:
                        if '<code>...</code>' in file_data:
                            pass # PR with many files. some did not get analyzed
                        else:
                            get_logger().warning(f"Failed to parse description", artifact={'description': file_data})
                except Exception as e:
                    get_logger().exception(f"Failed to process description: {e}", artifact={'description': file_data})


    except Exception as e:
        get_logger().exception(f"Failed to process description: {e}")

    return base_description_str, files


def get_version() -> str:
    # First check pyproject.toml if running directly out of repository
    if os.path.exists("pyproject.toml"):
        if sys.version_info >= (3, 11):
            import tomllib
            with open("pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                if "project" in data and "version" in data["project"]:
                    return data["project"]["version"]
                else:
                    get_logger().warning("Version not found in pyproject.toml")
        else:
            get_logger().warning("Unable to determine local version from pyproject.toml")

    # Otherwise get the installed pip package version
    try:
        return version('pr-agent')
    except PackageNotFoundError:
        get_logger().warning("Unable to find package named 'pr-agent'")
        return "unknown"


def replace_code_tags(text):
    """
    Replace odd instances of ` with <code> and even instances of ` with </code>
    """
    text = html.escape(text)
    parts = text.split('`')
    for i in range(1, len(parts), 2):
        parts[i] = '<code>' + parts[i] + '</code>'
    return ''.join(parts)
