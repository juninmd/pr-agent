import copy
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.utils import find_line_number_of_relevant_line_in_file

def create_inline_comment(body: str, relevant_file: str, relevant_line_in_file: str, diff_files, absolute_position: int = None, max_comment_chars=65000):
    body = body[:max_comment_chars]
    position, absolute_position = find_line_number_of_relevant_line_in_file(diff_files,
                                                                            relevant_file.strip('`'),
                                                                            relevant_line_in_file,
                                                                            absolute_position)
    if position == -1:
        get_logger().info(f"Could not find position for {relevant_file} {relevant_line_in_file}")
        subject_type = "FILE"
    else:
        subject_type = "LINE"
    path = relevant_file.strip()
    return dict(body=body, path=path, position=position) if subject_type == "LINE" else {}

def try_fix_invalid_inline_comments(invalid_comments: list[dict]) -> list[dict]:
    """
    Try fixing invalid comments by removing the suggestion part and setting the comment just on the first line.
    Return only comments that have been modified in some way.
    This is a best-effort attempt to fix invalid comments, and should be verified accordingly.
    """
    fixed_comments = []
    for comment in invalid_comments:
        try:
            fixed_comment = copy.deepcopy(comment)  # avoid modifying the original comment dict for later logging
            if "```suggestion" in comment["body"]:
                fixed_comment["body"] = comment["body"].split("```suggestion")[0]
            if "start_line" in comment:
                fixed_comment["line"] = comment["start_line"]
                del fixed_comment["start_line"]
            if "start_side" in comment:
                fixed_comment["side"] = comment["start_side"]
                del fixed_comment["start_side"]
            if fixed_comment != comment:
                fixed_comments.append(fixed_comment)
        except Exception as e:
            get_logger().error(f"Failed to fix inline comment, error: {e}")
    return fixed_comments
