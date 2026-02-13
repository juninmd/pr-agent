from __future__ import annotations

from pr_agent.algo.types import PRReviewHeader
from pr_agent.config_loader import get_settings
from pr_agent.algo.markdown_utils.compliance_formatter import ticket_markdown_logic
from pr_agent.algo.markdown_utils.review_formatter import (
    _process_contribution_time_estimate, _process_estimated_effort,
    _process_key_issues, _process_relevant_tests, _process_security_concerns,
    _process_todo_sections, process_can_be_split
)


def convert_to_markdown_v2(output_data: dict,
                           gfm_supported: bool = True,
                           incremental_review=None,
                           git_provider=None,
                           files=None) -> str:
    """
    Convert a dictionary of data into markdown format.
    Args:
        output_data (dict): A dictionary containing data to be converted to markdown format.
    Returns:
        str: The markdown formatted text generated from the input dictionary.
    """

    emojis = {
        "Can be split": "🔀",
        "Key issues to review": "⚡",
        "Recommended focus areas for review": "⚡",
        "Score": "🏅",
        "Relevant tests": "🧪",
        "Focused PR": "✨",
        "Relevant ticket": "🎫",
        "Security concerns": "🔒",
        "Todo sections": "📝",
        "Insights from user's answers": "📝",
        "Code feedback": "🤖",
        "Estimated effort to review [1-5]": "⏱️",
        "Contribution time cost estimate": "⏳",
        "Ticket compliance check": "🎫",
    }
    markdown_text = ""
    if not incremental_review:
        markdown_text += f"{PRReviewHeader.REGULAR.value} 🔍\n\n"
    else:
        markdown_text += f"{PRReviewHeader.INCREMENTAL.value} 🔍\n\n"
        markdown_text += f"⏮️ Review for commits since previous PR-Agent review {incremental_review}.\n\n"
    if not output_data or not output_data.get('review', {}):
        return ""

    if get_settings().get("pr_reviewer.enable_intro_text", False):
        markdown_text += f"Here are some key observations to aid the review process:\n\n"

    if gfm_supported:
        markdown_text += "<table>\n"

    todo_summary = output_data['review'].pop('todo_summary', '')
    for key, value in output_data['review'].items():
        if value is None or value == '' or value == {} or value == []:
            if key.lower() not in ['can_be_split', 'key_issues_to_review']:
                continue
        key_nice = key.replace('_', ' ').capitalize()
        emoji = emojis.get(key_nice, "")

        if 'Estimated effort to review' in key_nice:
            markdown_text += _process_estimated_effort(key_nice, value, emoji, gfm_supported)
        elif 'relevant tests' in key_nice.lower():
            markdown_text += _process_relevant_tests(key_nice, value, emoji, gfm_supported)
        elif 'ticket compliance check' in key_nice.lower():
            markdown_text = ticket_markdown_logic(emoji, markdown_text, value, gfm_supported)
        elif 'contribution time cost estimate' in key_nice.lower():
            markdown_text += _process_contribution_time_estimate(key_nice, value, emoji, gfm_supported)
        elif 'security concerns' in key_nice.lower():
            markdown_text += _process_security_concerns(key_nice, value, emoji, gfm_supported)
        elif 'todo sections' in key_nice.lower():
            markdown_text += _process_todo_sections(key_nice, value, emoji, gfm_supported, git_provider)
        elif 'can be split' in key_nice.lower():
            if gfm_supported:
                markdown_text += f"<tr><td>"
                markdown_text += process_can_be_split(emoji, value)
                markdown_text += f"</td></tr>\n"
        elif 'key issues to review' in key_nice.lower():
            markdown_text += _process_key_issues(key_nice, value, emoji, gfm_supported, git_provider, files)
        else:
            if gfm_supported:
                markdown_text += f"<tr><td>"
                markdown_text += f"{emoji}&nbsp;<strong>{key_nice}</strong>: {value}"
                markdown_text += f"</td></tr>\n"
            else:
                markdown_text += f"### {emoji} {key_nice}: {value}\n\n"

    if gfm_supported:
        markdown_text += "</table>\n"

    return markdown_text
