import re

def apply_git_merge_diff(original_content: str, merge_diff: str) -> str:
    """
    Applies a git merge diff to the original content.
    The diff should contain blocks like:
    <<<<<<< SEARCH
    original code
    =======
    new code
    >>>>>>> REPLACE
    """
    pattern = re.compile(
        r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
        re.DOTALL
    )

    new_content = original_content
    found_any = False

    for match in pattern.finditer(merge_diff):
        found_any = True
        search_block = match.group(1)
        replace_block = match.group(2)

        if search_block in new_content:
            new_content = new_content.replace(search_block, replace_block, 1)
        else:
            # Try with stripped whitespace if exact match fails?
            # For now, strict adherence to what was read is best.
            # But sometimes LLMs mess up indentation slightly.
            raise ValueError(f"Could not find search block in the file content.\nSearch Block:\n{search_block}")

    if not found_any:
        # Check if the diff format was wrong or just empty
        if "<<<<<<< SEARCH" in merge_diff:
             raise ValueError("Found conflict markers but failed to parse. Check format.")

    return new_content
