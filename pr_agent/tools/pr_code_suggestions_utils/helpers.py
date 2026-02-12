import textwrap
import copy
import re
from typing import List, Dict
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.utils import replace_code_tags
from pr_agent.tools.pr_description import insert_br_after_x_chars
from pr_agent.git_providers.git_provider import GitProvider
import difflib

def dedent_code(relevant_file, relevant_lines_start, new_code_snippet, git_provider):
    try:  # dedent code snippet
        diff_files = git_provider.diff_files if git_provider.diff_files \
            else git_provider.get_diff_files()
        original_initial_line = None
        for file in diff_files:
            if file.filename.strip() == relevant_file:
                if file.head_file:
                    file_lines = file.head_file.splitlines()
                    if relevant_lines_start > len(file_lines):
                        get_logger().warning(
                            "Could not dedent code snippet, because relevant_lines_start is out of range",
                            artifact={'filename': file.filename,
                                      'file_content': file.head_file,
                                      'relevant_lines_start': relevant_lines_start,
                                      'new_code_snippet': new_code_snippet})
                        return new_code_snippet
                    else:
                        original_initial_line = file_lines[relevant_lines_start - 1]
                else:
                    get_logger().warning("Could not dedent code snippet, because head_file is missing",
                                         artifact={'filename': file.filename,
                                                   'relevant_lines_start': relevant_lines_start,
                                                   'new_code_snippet': new_code_snippet})
                    return new_code_snippet
                break
        if original_initial_line:
            suggested_initial_line = new_code_snippet.splitlines()[0]
            original_initial_spaces = len(original_initial_line) - len(original_initial_line.lstrip()) # lstrip works both for spaces and tabs
            suggested_initial_spaces = len(suggested_initial_line) - len(suggested_initial_line.lstrip())
            delta_spaces = original_initial_spaces - suggested_initial_spaces
            if delta_spaces > 0:
                # Detect indentation character from original line
                indent_char = '\t' if original_initial_line.startswith('\t') else ' '
                new_code_snippet = textwrap.indent(new_code_snippet, delta_spaces * indent_char).rstrip('\n')
    except Exception as e:
        get_logger().error(f"Error when dedenting code snippet for file {relevant_file}, error: {e}")

    return new_code_snippet

def remove_line_numbers(patches_diff_list: List[str]) -> List[str]:
    # create a copy of the patches_diff_list, without line numbers for '__new hunk__' sections
    try:
        patches_diff_list_no_line_numbers = []
        for patches_diff in patches_diff_list:
            patches_diff_lines = patches_diff.splitlines()
            for i, line in enumerate(patches_diff_lines):
                if line.strip():
                    if line.isnumeric():
                        patches_diff_lines[i] = ''
                    elif line[0].isdigit():
                        # find the first letter in the line that starts with a valid letter
                        for j, char in enumerate(line):
                            if not char.isdigit():
                                patches_diff_lines[i] = line[j + 1:]
                                break
            patches_diff_list_no_line_numbers.append('\n'.join(patches_diff_lines))
        return patches_diff_list_no_line_numbers
    except Exception as e:
        get_logger().error(f"Error removing line numbers from patches_diff_list, error: {e}")
        return patches_diff_list

def validate_one_liner_suggestion_not_repeating_code(suggestion, git_provider):
    try:
        existing_code = suggestion.get('existing_code', '').strip()
        if '...' in existing_code:
            return suggestion
        new_code = suggestion.get('improved_code', '').strip()

        relevant_file = suggestion.get('relevant_file', '').strip()
        diff_files = git_provider.get_diff_files()
        for file in diff_files:
            if file.filename.strip() == relevant_file:
                # protections
                if not file.head_file:
                    get_logger().info(f"head_file is empty")
                    return suggestion
                head_file = file.head_file
                base_file = file.base_file
                if existing_code in base_file and existing_code not in head_file and new_code in head_file:
                    suggestion["score"] = 0
                    get_logger().warning(
                        f"existing_code is in the base file but not in the head file, setting score to 0",
                        artifact={"suggestion": suggestion})
    except Exception as e:
        get_logger().exception(f"Error validating one-liner suggestion", artifact={"error": e})

    return suggestion

def truncate_if_needed(suggestion):
    max_code_suggestion_length = get_settings().get("PR_CODE_SUGGESTIONS.MAX_CODE_SUGGESTION_LENGTH", 0)
    suggestion_truncation_message = get_settings().get("PR_CODE_SUGGESTIONS.SUGGESTION_TRUNCATION_MESSAGE", "")
    if max_code_suggestion_length > 0:
        if len(suggestion['improved_code']) > max_code_suggestion_length:
            get_logger().info(f"Truncated suggestion from {len(suggestion['improved_code'])} "
                              f"characters to {max_code_suggestion_length} characters")
            suggestion['improved_code'] = suggestion['improved_code'][:max_code_suggestion_length]
            suggestion['improved_code'] += f"\n{suggestion_truncation_message}"
    return suggestion

def extract_link(s):
    r = re.compile(r"<!--.*?-->")
    match = r.search(s)

    up_to_commit_txt = ""
    if match:
        up_to_commit_txt = f" up to commit {match.group(0)[4:-3].strip()}"
    return up_to_commit_txt

def get_score_str(score: int) -> str:
    th_high = get_settings().pr_code_suggestions.get('new_score_mechanism_th_high', 9)
    th_medium = get_settings().pr_code_suggestions.get('new_score_mechanism_th_medium', 7)
    if score >= th_high:
        return "High"
    elif score >= th_medium:
        return "Medium"
    else:  # score < 7
        return "Low"

def generate_summarized_suggestions(data: Dict, git_provider) -> str:
    try:
        pr_body = "## PR Code Suggestions ✨\n\n"

        if len(data.get('code_suggestions', [])) == 0:
            pr_body += "No suggestions found to improve this PR."
            return pr_body

        if get_settings().config.is_auto_command:
            pr_body += "Explore these optional code suggestions:\n\n"

        language_extension_map_org = get_settings().language_extension_map_org
        extension_to_language = {}
        for language, extensions in language_extension_map_org.items():
            for ext in extensions:
                extension_to_language[ext] = language

        pr_body += "<table>"
        header = f"Suggestion"
        delta = 66
        header += "&nbsp; " * delta
        pr_body += f"""<thead><tr><td><strong>Category</strong></td><td align=left><strong>{header}</strong></td><td align=center><strong>Impact</strong></td></tr>"""
        pr_body += """<tbody>"""
        suggestions_labels = dict()
        # add all suggestions related to each label
        for suggestion in data['code_suggestions']:
            label = suggestion['label'].strip().strip("'").strip('"')
            if label not in suggestions_labels:
                suggestions_labels[label] = []
            suggestions_labels[label].append(suggestion)

        # sort suggestions_labels by the suggestion with the highest score
        suggestions_labels = dict(
            sorted(suggestions_labels.items(), key=lambda x: max([s['score'] for s in x[1]]), reverse=True))
        # sort the suggestions inside each label group by score
        for label, suggestions in suggestions_labels.items():
            suggestions_labels[label] = sorted(suggestions, key=lambda x: x['score'], reverse=True)

        counter_suggestions = 0
        for label, suggestions in suggestions_labels.items():
            num_suggestions = len(suggestions)
            pr_body += f"""<tr><td rowspan={num_suggestions}>{label.capitalize()}</td>\n"""
            for i, suggestion in enumerate(suggestions):

                relevant_file = suggestion['relevant_file'].strip()
                relevant_lines_start = int(suggestion['relevant_lines_start'])
                relevant_lines_end = int(suggestion['relevant_lines_end'])
                range_str = ""
                if relevant_lines_start == relevant_lines_end:
                    range_str = f"[{relevant_lines_start}]"
                else:
                    range_str = f"[{relevant_lines_start}-{relevant_lines_end}]"

                try:
                    code_snippet_link = git_provider.get_line_link(relevant_file, relevant_lines_start,
                                                                        relevant_lines_end)
                except:
                    code_snippet_link = ""
                # add html table for each suggestion

                suggestion_content = suggestion['suggestion_content'].rstrip()
                CHAR_LIMIT_PER_LINE = 84
                suggestion_content = insert_br_after_x_chars(suggestion_content, CHAR_LIMIT_PER_LINE)
                # pr_body += f"<tr><td><details><summary>{suggestion_content}</summary>"
                existing_code = suggestion['existing_code'].rstrip() + "\n"
                improved_code = suggestion['improved_code'].rstrip() + "\n"

                diff = difflib.unified_diff(existing_code.split('\n'),
                                            improved_code.split('\n'), n=999)
                patch_orig = "\n".join(diff)
                patch = "\n".join(patch_orig.splitlines()[5:]).strip('\n')

                example_code = ""
                example_code += f"```diff\n{patch.rstrip()}\n```\n"
                if i == 0:
                    pr_body += f"""<td>\n\n"""
                else:
                    pr_body += f"""<tr><td>\n\n"""
                suggestion_summary = suggestion['one_sentence_summary'].strip().rstrip('.')
                if "'<" in suggestion_summary and ">'" in suggestion_summary:
                    # escape the '<' and '>' characters, otherwise they are interpreted as html tags
                    get_logger().info(f"Escaped suggestion summary: {suggestion_summary}")
                    suggestion_summary = suggestion_summary.replace("'<", "`<")
                    suggestion_summary = suggestion_summary.replace(">'", ">`")
                if '`' in suggestion_summary:
                    suggestion_summary = replace_code_tags(suggestion_summary)

                pr_body += f"""\n\n<details><summary>{suggestion_summary}</summary>\n\n___\n\n"""
                pr_body += f"""
**{suggestion_content}**

[{relevant_file} {range_str}]({code_snippet_link})

{example_code.rstrip()}
"""
                if suggestion.get('score_why'):
                    pr_body += f"<details><summary>Suggestion importance[1-10]: {suggestion['score']}</summary>\n\n"
                    pr_body += f"__\n\nWhy: {suggestion['score_why']}\n\n"
                    pr_body += f"</details>"

                pr_body += f"</details>"

                # # add another column for 'score'
                score_int = int(suggestion.get('score', 0))
                score_str = f"{score_int}"
                if get_settings().pr_code_suggestions.new_score_mechanism:
                    score_str = get_score_str(score_int)
                pr_body += f"</td><td align=center>{score_str}\n\n"

                pr_body += f"</td></tr>"
                counter_suggestions += 1

            # pr_body += "</details>"
            # pr_body += """</td></tr>"""
        pr_body += """</tr></tbody></table>"""
        return pr_body
    except Exception as e:
        get_logger().info(f"Failed to publish summarized code suggestions, error: {e}")
        return ""

def add_self_review_text(pr_body):
    text = get_settings().pr_code_suggestions.code_suggestions_self_review_text
    pr_body += f"\n\n- [ ]  {text}"
    approve_pr_on_self_review = get_settings().pr_code_suggestions.approve_pr_on_self_review
    fold_suggestions_on_self_review = get_settings().pr_code_suggestions.fold_suggestions_on_self_review
    if approve_pr_on_self_review and not fold_suggestions_on_self_review:
        pr_body += ' <!-- approve pr self-review -->'
    elif fold_suggestions_on_self_review and not approve_pr_on_self_review:
        pr_body += ' <!-- fold suggestions self-review -->'
    else:
        pr_body += ' <!-- approve and fold suggestions self-review -->'
    return pr_body

def publish_persistent_comment_with_history(git_provider: GitProvider,
                                            pr_comment: str,
                                            initial_header: str,
                                            update_header: bool = True,
                                            name='review',
                                            final_update_message=True,
                                            max_previous_comments=4,
                                            progress_response=None,
                                            only_fold=False):

    def _extract_link(comment_text: str):
        r = re.compile(r"<!--.*?-->")
        match = r.search(comment_text)

        up_to_commit_txt = ""
        if match:
            up_to_commit_txt = f" up to commit {match.group(0)[4:-3].strip()}"
        return up_to_commit_txt

    history_header = f"#### Previous suggestions\n"
    last_commit_num = git_provider.get_latest_commit_url().split('/')[-1][:7]
    if only_fold: # A user clicked on the 'self-review' checkbox
        text = get_settings().pr_code_suggestions.code_suggestions_self_review_text
        latest_suggestion_header = f"\n\n- [x]  {text}"
    else:
        latest_suggestion_header = f"Latest suggestions up to {last_commit_num}"
    latest_commit_html_comment = f"<!-- {last_commit_num} -->"
    found_comment = None

    if max_previous_comments > 0:
        try:
            prev_comments = list(git_provider.get_issue_comments())
            for comment in prev_comments:
                if comment.body.startswith(initial_header):
                    prev_suggestions = comment.body
                    found_comment = comment
                    comment_url = git_provider.get_comment_url(comment)

                    if history_header.strip() not in comment.body:
                        # no history section
                        # extract everything between <table> and </table> in comment.body including <table> and </table>
                        table_index = comment.body.find("<table>")
                        if table_index == -1:
                            git_provider.edit_comment(comment, pr_comment)
                            continue
                        # find http link from comment.body[:table_index]
                        up_to_commit_txt = _extract_link(comment.body[:table_index])
                        prev_suggestion_table = comment.body[
                                                table_index:comment.body.rfind("</table>") + len("</table>")]

                        tick = "✅ " if "✅" in prev_suggestion_table else ""
                        # surround with details tag
                        prev_suggestion_table = f"<details><summary>{tick}{name.capitalize()}{up_to_commit_txt}</summary>\n<br>{prev_suggestion_table}\n\n</details>"

                        new_suggestion_table = pr_comment.replace(initial_header, "").strip()

                        pr_comment_updated = f"{initial_header}\n{latest_commit_html_comment}\n\n"
                        pr_comment_updated += f"{latest_suggestion_header}\n{new_suggestion_table}\n\n___\n\n"
                        pr_comment_updated += f"{history_header}{prev_suggestion_table}\n"
                    else:
                        # get the text of the previous suggestions until the latest commit
                        sections = prev_suggestions.split(history_header.strip())
                        latest_table = sections[0].strip()
                        prev_suggestion_table = sections[1].replace(history_header, "").strip()

                        # get text after the latest_suggestion_header in comment.body
                        table_ind = latest_table.find("<table>")
                        up_to_commit_txt = _extract_link(latest_table[:table_ind])

                        latest_table = latest_table[table_ind:latest_table.rfind("</table>") + len("</table>")]
                        # enforce max_previous_comments
                        count = prev_suggestions.count(f"\n<details><summary>{name.capitalize()}")
                        count += prev_suggestions.count(f"\n<details><summary>✅ {name.capitalize()}")
                        if count >= max_previous_comments:
                            # remove the oldest suggestion
                            prev_suggestion_table = prev_suggestion_table[:prev_suggestion_table.rfind(
                                f"<details><summary>{name.capitalize()} up to commit")]

                        tick = "✅ " if "✅" in latest_table else ""
                        # Add to the prev_suggestions section
                        last_prev_table = f"\n<details><summary>{tick}{name.capitalize()}{up_to_commit_txt}</summary>\n<br>{latest_table}\n\n</details>"
                        prev_suggestion_table = last_prev_table + "\n" + prev_suggestion_table

                        new_suggestion_table = pr_comment.replace(initial_header, "").strip()

                        pr_comment_updated = f"{initial_header}\n"
                        pr_comment_updated += f"{latest_commit_html_comment}\n\n"
                        pr_comment_updated += f"{latest_suggestion_header}\n\n{new_suggestion_table}\n\n"
                        pr_comment_updated += "___\n\n"
                        pr_comment_updated += f"{history_header}\n"
                        pr_comment_updated += f"{prev_suggestion_table}\n"

                    get_logger().info(f"Persistent mode - updating comment {comment_url} to latest {name} message")
                    if progress_response:  # publish to 'progress_response' comment, because it refreshes immediately
                        git_provider.edit_comment(progress_response, pr_comment_updated)
                        git_provider.remove_comment(comment)
                        comment = progress_response
                    else:
                        git_provider.edit_comment(comment, pr_comment_updated)
                    return comment
        except Exception as e:
            get_logger().exception(f"Failed to update persistent review, error: {e}")
            pass

    # if we are here, we did not find a previous comment to update
    body = pr_comment.replace(initial_header, "").strip()
    pr_comment = f"{initial_header}\n\n{latest_commit_html_comment}\n\n{body}\n\n"
    if progress_response:
        git_provider.edit_comment(progress_response, pr_comment)
        new_comment = progress_response
    else:
        new_comment = git_provider.publish_comment(pr_comment)
    return new_comment
