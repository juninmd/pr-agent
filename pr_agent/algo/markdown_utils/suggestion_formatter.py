from __future__ import annotations

import textwrap

from pr_agent.log import get_logger


def parse_code_suggestion(code_suggestion: dict, i: int = 0, gfm_supported: bool = True) -> str:
    """
    Convert a dictionary of data into markdown format.

    Args:
        code_suggestion (dict): A dictionary containing data to be converted to markdown format.

    Returns:
        str: A string containing the markdown formatted text generated from the input dictionary.
    """
    markdown_text = ""
    if gfm_supported and 'relevant_line' in code_suggestion:
        markdown_text += '<table>'
        for sub_key, sub_value in code_suggestion.items():
            try:
                if sub_key.lower() == 'relevant_file':
                    relevant_file = sub_value.strip('`').strip('"').strip("'")
                    markdown_text += f"<tr><td>relevant file</td><td>{relevant_file}</td></tr>"
                    # continue
                elif sub_key.lower() == 'suggestion':
                    markdown_text += (f"<tr><td>{sub_key} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</td>"
                                      f"<td>\n\n<strong>\n\n{sub_value.strip()}\n\n</strong>\n</td></tr>")
                elif sub_key.lower() == 'relevant_line':
                    markdown_text += f"<tr><td>relevant line</td>"
                    sub_value_list = sub_value.split('](')
                    relevant_line = sub_value_list[0].lstrip('`').lstrip('[')
                    if len(sub_value_list) > 1:
                        link = sub_value_list[1].rstrip(')').strip('`')
                        markdown_text += f"<td><a href='{link}'>{relevant_line}</a></td>"
                    else:
                        markdown_text += f"<td>{relevant_line}</td>"
                    markdown_text += "</tr>"
            except Exception as e:
                get_logger().exception(f"Failed to parse code suggestion: {e}")
                pass
        markdown_text += '</table>'
        markdown_text += "<hr>"
    else:
        for sub_key, sub_value in code_suggestion.items():
            if isinstance(sub_key, str):
                sub_key = sub_key.rstrip()
            if isinstance(sub_value,str):
                sub_value = sub_value.rstrip()
            if isinstance(sub_value, dict):  # "code example"
                markdown_text += f"  - **{sub_key}:**\n"
                for code_key, code_value in sub_value.items():  # 'before' and 'after' code
                    code_str = f"```\n{code_value}\n```"
                    code_str_indented = textwrap.indent(code_str, '        ')
                    markdown_text += f"    - **{code_key}:**\n{code_str_indented}\n"
            else:
                if "relevant_file" in sub_key.lower():
                    markdown_text += f"\n  - **{sub_key}:** {sub_value}  \n"
                else:
                    markdown_text += f"   **{sub_key}:** {sub_value}  \n"
                if "relevant_line" not in sub_key.lower():  # nicer presentation
                    # markdown_text = markdown_text.rstrip('\n') + "\\\n" # works for gitlab
                    markdown_text = markdown_text.rstrip('\n') + "   \n"  # works for gitlab and bitbucker

        markdown_text += "\n"
    return markdown_text
