from __future__ import annotations

import textwrap

from pr_agent.algo.git_patch_processing import extract_hunk_lines_from_patch
from pr_agent.algo.language_handler import set_file_languages
from pr_agent.algo.types import TodoItem
from pr_agent.log import get_logger


def is_value_no(value):
    if not value:
        return True
    value_str = str(value).strip().lower()
    if value_str == 'no' or value_str == 'none' or value_str == 'false':
        return True
    return False


def emphasize_header(text: str, only_markdown=False, reference_link=None) -> str:
    try:
        # Finding the position of the first occurrence of ": "
        colon_position = text.find(": ")

        # Splitting the string and wrapping the first part in <strong> tags
        if colon_position != -1:
            # Everything before the colon (inclusive) is wrapped in <strong> tags
            if only_markdown:
                if reference_link:
                    transformed_string = f"[**{text[:colon_position + 1]}**]({reference_link})\n" + text[colon_position + 1:]
                else:
                    transformed_string = f"**{text[:colon_position + 1]}**\n" + text[colon_position + 1:]
            else:
                if reference_link:
                    transformed_string = f"<strong><a href='{reference_link}'>{text[:colon_position + 1]}</a></strong><br>" + text[colon_position + 1:]
                else:
                    transformed_string = "<strong>" + text[:colon_position + 1] + "</strong>" +'<br>' + text[colon_position + 1:]
        else:
            # If there's no ": ", return the original string
            transformed_string = text

        return transformed_string
    except Exception as e:
        get_logger().exception(f"Failed to emphasize header: {e}")
        return text


def extract_relevant_lines_str(end_line, files, relevant_file, start_line, dedent=False) -> str:
    """
    Finds 'relevant_file' in 'files', and extracts the lines from 'start_line' to 'end_line' string from the file content.
    """
    try:
        relevant_lines_str = ""
        if files:
            files = set_file_languages(files)
            for file in files:
                if file.filename.strip() == relevant_file:
                    if not file.head_file:
                        # as a fallback, extract relevant lines directly from patch
                        patch = file.patch
                        get_logger().info(f"No content found in file: '{file.filename}' for 'extract_relevant_lines_str'. Using patch instead")
                        _, selected_lines = extract_hunk_lines_from_patch(patch, file.filename, start_line, end_line,side='right')
                        if not selected_lines:
                            get_logger().error(f"Failed to extract relevant lines from patch: {file.filename}")
                            return ""
                        # filter out '-' lines
                        relevant_lines_str = ""
                        for line in selected_lines.splitlines():
                            if line.startswith('-'):
                                continue
                            relevant_lines_str += line[1:] + '\n'
                    else:
                        relevant_file_lines = file.head_file.splitlines()
                        relevant_lines_str = "\n".join(relevant_file_lines[start_line - 1:end_line])

                    if dedent and relevant_lines_str:
                        # Remove the longest leading string of spaces and tabs common to all lines.
                        relevant_lines_str = textwrap.dedent(relevant_lines_str)
                    relevant_lines_str = f"```{file.language}\n{relevant_lines_str}\n```"
                    break

        return relevant_lines_str
    except Exception as e:
        get_logger().exception(f"Failed to extract relevant lines: {e}")
        return ""


def format_todo_item(todo_item: TodoItem, git_provider, gfm_supported) -> str:
    relevant_file = todo_item.get('relevant_file', '').strip()
    line_number = todo_item.get('line_number', '')
    content = todo_item.get('content', '')
    reference_link = git_provider.get_line_link(relevant_file, line_number, line_number)
    file_ref = f"{relevant_file} [{line_number}]"
    if reference_link:
        if gfm_supported:
            file_ref = f"<a href='{reference_link}'>{file_ref}</a>"
        else:
            file_ref = f"[{file_ref}]({reference_link})"

    if content:
        return f"{file_ref}: {content.strip()}"
    else:
        # if content is empty, return only the file reference
        return file_ref


def format_todo_items(value: list[TodoItem] | TodoItem, git_provider, gfm_supported) -> str:
    markdown_text = ""
    MAX_ITEMS = 5 # limit the number of items to display
    if gfm_supported:
        if isinstance(value, list):
            markdown_text += "<ul>\n"
            if len(value) > MAX_ITEMS:
                get_logger().debug(f"Truncating todo items to {MAX_ITEMS} items")
                value = value[:MAX_ITEMS]
            for todo_item in value:
                markdown_text += f"<li>{format_todo_item(todo_item, git_provider, gfm_supported)}</li>\n"
            markdown_text += "</ul>\n"
        else:
            markdown_text += f"<p>{format_todo_item(value, git_provider, gfm_supported)}</p>\n"
    else:
        if isinstance(value, list):
            if len(value) > MAX_ITEMS:
                get_logger().debug(f"Truncating todo items to {MAX_ITEMS} items")
                value = value[:MAX_ITEMS]
            for todo_item in value:
                markdown_text += f"- {format_todo_item(todo_item, git_provider, gfm_supported)}\n"
        else:
            markdown_text += f"- {format_todo_item(value, git_provider, gfm_supported)}\n"
    return markdown_text
