from __future__ import annotations

from pr_agent.algo.markdown_utils.utils import (
    emphasize_header, extract_relevant_lines_str, format_todo_items,
    is_value_no
)
from pr_agent.log import get_logger


def _process_estimated_effort(key_nice, value, emoji, gfm_supported):
    key_nice = 'Estimated effort to review'
    markdown_text = ""
    value = str(value).strip()
    if value.isnumeric():
        value_int = int(value)
    else:
        try:
            value_int = int(value.split(',')[0])
        except ValueError:
            value_int = 0

    if value_int > 0:
        blue_bars = '🔵' * value_int
        white_bars = '⚪' * (5 - value_int)
        value = f"{value_int} {blue_bars}{white_bars}"

    if gfm_supported:
        markdown_text += f"<tr><td>"
        markdown_text += f"{emoji}&nbsp;<strong>{key_nice}</strong>: {value}"
        markdown_text += f"</td></tr>\n"
    else:
        markdown_text += f"### {emoji} {key_nice}: {value}\n\n"
    return markdown_text

def _process_relevant_tests(key_nice, value, emoji, gfm_supported):
    markdown_text = ""
    value = str(value).strip().lower()
    if gfm_supported:
        markdown_text += f"<tr><td>"
        if is_value_no(value):
            markdown_text += f"{emoji}&nbsp;<strong>No relevant tests</strong>"
        else:
            markdown_text += f"{emoji}&nbsp;<strong>PR contains tests</strong>"
        markdown_text += f"</td></tr>\n"
    else:
        if is_value_no(value):
            markdown_text += f'### {emoji} No relevant tests\n\n'
        else:
            markdown_text += f"### {emoji} PR contains tests\n\n"
    return markdown_text

def _process_contribution_time_estimate(key_nice, value, emoji, gfm_supported):
    markdown_text = ""
    if gfm_supported:
        markdown_text += f"<tr><td>{emoji}&nbsp;<strong>Contribution time estimate</strong> (best, average, worst case): "
        markdown_text += f"{value['best_case'].replace('m', ' minutes')} | {value['average_case'].replace('m', ' minutes')} | {value['worst_case'].replace('m', ' minutes')}"
        markdown_text += f"</td></tr>\n"
    else:
        markdown_text += f"### {emoji} Contribution time estimate (best, average, worst case): "
        markdown_text += f"{value['best_case'].replace('m', ' minutes')} | {value['average_case'].replace('m', ' minutes')} | {value['worst_case'].replace('m', ' minutes')}\n\n"
    return markdown_text

def _process_security_concerns(key_nice, value, emoji, gfm_supported):
    markdown_text = ""
    if gfm_supported:
        markdown_text += f"<tr><td>"
        if is_value_no(value):
            markdown_text += f"{emoji}&nbsp;<strong>No security concerns identified</strong>"
        else:
            markdown_text += f"{emoji}&nbsp;<strong>Security concerns</strong><br><br>\n\n"
            value = emphasize_header(value.strip())
            markdown_text += f"{value}"
        markdown_text += f"</td></tr>\n"
    else:
        if is_value_no(value):
            markdown_text += f'### {emoji} No security concerns identified\n\n'
        else:
            markdown_text += f"### {emoji} Security concerns\n\n"
            value = emphasize_header(value.strip(), only_markdown=True)
            markdown_text += f"{value}\n\n"
    return markdown_text

def _process_todo_sections(key_nice, value, emoji, gfm_supported, git_provider):
    markdown_text = ""
    if gfm_supported:
        markdown_text += "<tr><td>"
        if is_value_no(value):
            markdown_text += f"✅&nbsp;<strong>No TODO sections</strong>"
        else:
            markdown_todo_items = format_todo_items(value, git_provider, gfm_supported)
            markdown_text += f"{emoji}&nbsp;<strong>TODO sections</strong>\n<br><br>\n"
            markdown_text += markdown_todo_items
        markdown_text += "</td></tr>\n"
    else:
        if is_value_no(value):
            markdown_text += f"### ✅ No TODO sections\n\n"
        else:
            markdown_todo_items = format_todo_items(value, git_provider, gfm_supported)
            markdown_text += f"### {emoji} TODO sections\n\n"
            markdown_text += markdown_todo_items
    return markdown_text

def _process_key_issues(key_nice, value, emoji, gfm_supported, git_provider, files):
    markdown_text = ""
    # value is a list of issues
    if is_value_no(value):
        if gfm_supported:
            markdown_text += f"<tr><td>"
            markdown_text += f"{emoji}&nbsp;<strong>No major issues detected</strong>"
            markdown_text += f"</td></tr>\n"
        else:
            markdown_text += f"### {emoji} No major issues detected\n\n"
    else:
        issues = value
        if gfm_supported:
            markdown_text += f"<tr><td>"
            markdown_text += f"{emoji}&nbsp;<strong>Recommended focus areas for review</strong><br><br>\n\n"
        else:
            markdown_text += f"### {emoji} Recommended focus areas for review\n\n#### \n"
        for i, issue in enumerate(issues):
            try:
                if not issue or not isinstance(issue, dict):
                    continue
                relevant_file = issue.get('relevant_file', '').strip()
                issue_header = issue.get('issue_header', '').strip()
                if issue_header.lower() == 'possible bug':
                    issue_header = 'Possible Issue'  # Make the header less frightening
                issue_content = issue.get('issue_content', '').strip()
                start_line = int(str(issue.get('start_line', 0)).strip())
                end_line = int(str(issue.get('end_line', 0)).strip())

                relevant_lines_str = extract_relevant_lines_str(end_line, files, relevant_file, start_line, dedent=True)
                if git_provider:
                    reference_link = git_provider.get_line_link(relevant_file, start_line, end_line)
                else:
                    reference_link = None

                if gfm_supported:
                    if reference_link is not None and len(reference_link) > 0:
                        if relevant_lines_str:
                            issue_str = f"<details><summary><a href='{reference_link}'><strong>{issue_header}</strong></a>\n\n{issue_content}\n</summary>\n\n{relevant_lines_str}\n\n</details>"
                        else:
                            issue_str = f"<a href='{reference_link}'><strong>{issue_header}</strong></a><br>{issue_content}"
                    else:
                        issue_str = f"<strong>{issue_header}</strong><br>{issue_content}"
                else:
                    if reference_link is not None and len(reference_link) > 0:
                        issue_str = f"[**{issue_header}**]({reference_link})\n\n{issue_content}\n\n"
                    else:
                        issue_str = f"**{issue_header}**\n\n{issue_content}\n\n"
                markdown_text += f"{issue_str}\n\n"
            except Exception as e:
                get_logger().exception(f"Failed to process 'Recommended focus areas for review': {e}")
        if gfm_supported:
            markdown_text += f"</td></tr>\n"
    return markdown_text

def process_can_be_split(emoji, value):
    try:
        # key_nice = "Can this PR be split?"
        key_nice = "Multiple PR themes"
        markdown_text = ""
        if not value or isinstance(value, list) and len(value) == 1:
            value = "No"
            # markdown_text += f"<tr><td> {emoji}&nbsp;<strong>{key_nice}</strong></td><td>\n\n{value}\n\n</td></tr>\n"
            # markdown_text += f"### {emoji} No multiple PR themes\n\n"
            markdown_text += f"{emoji} <strong>No multiple PR themes</strong>\n\n"
        else:
            markdown_text += f"{emoji} <strong>{key_nice}</strong><br><br>\n\n"
            for i, split in enumerate(value):
                title = split.get('title', '')
                relevant_files = split.get('relevant_files', [])
                markdown_text += f"<details><summary>\nSub-PR theme: <b>{title}</b></summary>\n\n"
                markdown_text += f"___\n\nRelevant files:\n\n"
                for file in relevant_files:
                    markdown_text += f"- {file}\n"
                markdown_text += f"___\n\n"
                markdown_text += f"</details>\n\n"
    except Exception as e:
        get_logger().exception(f"Failed to process can be split: {e}")
        return ""
    return markdown_text
