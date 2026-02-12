from __future__ import annotations

import re
import traceback

from pr_agent.algo.types import EDIT_TYPE
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger
from pr_agent.algo.patch_processor import PatchProcessor, extract_hunk_headers, RE_HUNK_HEADER


def extend_patch(original_file_str, patch_str, patch_extra_lines_before=0,
                 patch_extra_lines_after=0, filename: str = "", new_file_str="") -> str:
    if not patch_str or (patch_extra_lines_before == 0 and patch_extra_lines_after == 0) or not original_file_str:
        return patch_str

    original_file_str = decode_if_bytes(original_file_str)
    new_file_str = decode_if_bytes(new_file_str)
    if not original_file_str:
        return patch_str

    if should_skip_patch(filename):
        return patch_str

    try:
        processor = PatchProcessor(patch_str, original_file_str,
                                   patch_extra_lines_before, patch_extra_lines_after, new_file_str)
        extended_patch_str = processor.process()
    except Exception as e:
        get_logger().warning(f"Failed to extend patch: {e}", artifact={"traceback": traceback.format_exc()})
        return patch_str

    return extended_patch_str


def decode_if_bytes(original_file_str):
    if isinstance(original_file_str, (bytes, bytearray)):
        try:
            return original_file_str.decode('utf-8')
        except UnicodeDecodeError:
            encodings_to_try = ['iso-8859-1', 'latin-1', 'ascii', 'utf-16']
            for encoding in encodings_to_try:
                try:
                    return original_file_str.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return ""
    return original_file_str


def should_skip_patch(filename):
    patch_extension_skip_types = get_settings().config.patch_extension_skip_types
    if patch_extension_skip_types and filename:
        return any(filename.endswith(skip_type) for skip_type in patch_extension_skip_types)
    return False


def omit_deletion_hunks(patch_lines) -> str:
    """
    Omit deletion hunks from the patch and return the modified patch.
    Args:
    - patch_lines: a list of strings representing the lines of the patch
    Returns:
    - A string representing the modified patch with deletion hunks omitted
    """

    temp_hunk = []
    added_patched = []
    add_hunk = False
    inside_hunk = False

    for line in patch_lines:
        if line.startswith('@@'):
            match = RE_HUNK_HEADER.match(line)
            if match:
                # finish previous hunk
                if inside_hunk and add_hunk:
                    added_patched.extend(temp_hunk)
                    temp_hunk = []
                    add_hunk = False
                temp_hunk.append(line)
                inside_hunk = True
        else:
            temp_hunk.append(line)
            if line:
                edit_type = line[0]
                if edit_type == '+':
                    add_hunk = True
    if inside_hunk and add_hunk:
        added_patched.extend(temp_hunk)

    return '\n'.join(added_patched)


def handle_patch_deletions(patch: str, original_file_content_str: str,
                           new_file_content_str: str, file_name: str, edit_type: EDIT_TYPE = EDIT_TYPE.UNKNOWN) -> str:
    """
    Handle entire file or deletion patches.

    This function takes a patch, original file content, new file content, and file name as input.
    It handles entire file or deletion patches and returns the modified patch with deletion hunks omitted.

    Args:
        patch (str): The patch to be handled.
        original_file_content_str (str): The original content of the file.
        new_file_content_str (str): The new content of the file.
        file_name (str): The name of the file.

    Returns:
        str: The modified patch with deletion hunks omitted.

    """
    if not new_file_content_str and (edit_type == EDIT_TYPE.DELETED or edit_type == EDIT_TYPE.UNKNOWN):
        # logic for handling deleted files - don't show patch, just show that the file was deleted
        if get_settings().config.verbosity_level > 0:
            get_logger().info(f"Processing file: {file_name}, minimizing deletion file")
        patch = None # file was deleted
    else:
        patch_lines = patch.splitlines()
        patch_new = omit_deletion_hunks(patch_lines)
        if patch != patch_new:
            if get_settings().config.verbosity_level > 0:
                get_logger().info(f"Processing file: {file_name}, hunks were deleted")
            patch = patch_new
    return patch


def _process_hunk(patch_with_lines_list, new_content_lines, old_content_lines, start2):
    is_plus_lines = is_minus_lines = False
    if new_content_lines:
        is_plus_lines = any([line.startswith('+') for line in new_content_lines])
    if old_content_lines:
        is_minus_lines = any([line.startswith('-') for line in old_content_lines])

    if is_plus_lines or is_minus_lines:
        # notice 'True' here - we always present __new hunk__ for section, otherwise LLM gets confused
        # remove trailing newlines from last element if it exists
        if patch_with_lines_list and patch_with_lines_list[-1].endswith('\n'):
            patch_with_lines_list[-1] = patch_with_lines_list[-1].rstrip()
        patch_with_lines_list.append('\n__new hunk__\n')
        for i, line_new in enumerate(new_content_lines):
            patch_with_lines_list.append(f"{start2 + i} {line_new}\n")

    if is_minus_lines:
        # remove trailing newlines from last element if it exists
        if patch_with_lines_list and patch_with_lines_list[-1].endswith('\n'):
            patch_with_lines_list[-1] = patch_with_lines_list[-1].rstrip()
        patch_with_lines_list.append('\n__old hunk__\n')
        for line_old in old_content_lines:
            patch_with_lines_list.append(f"{line_old}\n")


def decouple_and_convert_to_hunks_with_lines_numbers(patch: str, file) -> str:
    """
    Convert a given patch string into a string with line numbers for each hunk, indicating the new and old content of
    the file.

    Args:
        patch (str): The patch string to be converted.
        file: An object containing the filename of the file being patched.

    Returns:
        str: A string with line numbers for each hunk, indicating the new and old content of the file.

    example output:
## src/file.ts
__new hunk__
881        line1
882        line2
883        line3
887 +      line4
888 +      line5
889        line6
890        line7
...
__old hunk__
        line1
        line2
-       line3
-       line4
        line5
        line6
           ...
    """

    # Add a header for the file
    if file:
        # if the file was deleted, return a message indicating that the file was deleted
        if hasattr(file, 'edit_type') and file.edit_type == EDIT_TYPE.DELETED:
            return f"\n\n## File '{file.filename.strip()}' was deleted\n"

        patch_with_lines_list = [f"\n\n## File: '{file.filename.strip()}'\n"]
    else:
        patch_with_lines_list = []

    patch_lines = patch.splitlines()
    new_content_lines = []
    old_content_lines = []
    match = None
    start1, size1, start2, size2 = -1, -1, -1, -1
    prev_header_line = []
    header_line = []

    for line_i, line in enumerate(patch_lines):
        # Optimization: only check lower() if line starts with backslash (standard for 'No newline...')
        if line.startswith('\\') and 'no newline at end of file' in line.lower():
            continue

        if line.startswith('@@'):
            header_line = line
            match = RE_HUNK_HEADER.match(line)
            if match and (new_content_lines or old_content_lines):  # found a new hunk, split the previous lines
                if prev_header_line:
                    patch_with_lines_list.append(f'\n{prev_header_line}\n')

                _process_hunk(patch_with_lines_list, new_content_lines, old_content_lines, start2)

                new_content_lines = []
                old_content_lines = []
            if match:
                prev_header_line = header_line

            section_header, size1, size2, start1, start2 = extract_hunk_headers(match)

        elif line.startswith('+'):
            new_content_lines.append(line)
        elif line.startswith('-'):
            old_content_lines.append(line)
        else:
            if not line and line_i: # if this line is empty and the next line is a hunk header, skip it
                if line_i + 1 < len(patch_lines) and patch_lines[line_i + 1].startswith('@@'):
                    continue
                elif line_i + 1 == len(patch_lines):
                    continue
            new_content_lines.append(line)
            old_content_lines.append(line)

    # finishing last hunk
    if match and new_content_lines:
        patch_with_lines_list.append(f'\n{header_line}\n')
        _process_hunk(patch_with_lines_list, new_content_lines, old_content_lines, start2)

    return "".join(patch_with_lines_list).rstrip()


def extract_hunk_lines_from_patch(patch: str, file_name, line_start, line_end, side, remove_trailing_chars: bool = True) -> tuple[str, str]:
    try:
        patch_with_lines_list = [f"\n\n## File: '{file_name.strip()}'\n\n"]
        selected_lines_list = []
        patch_lines = patch.splitlines()
        match = None
        start1, size1, start2, size2 = -1, -1, -1, -1
        skip_hunk = False
        selected_lines_num = 0
        side_lower = side.lower()

        for line in patch_lines:
            # Optimization: only check lower() if line starts with backslash (standard for 'No newline...')
            if line.startswith('\\') and 'no newline at end of file' in line.lower():
                continue

            if line.startswith('@@'):
                skip_hunk = False
                selected_lines_num = 0
                header_line = line

                match = RE_HUNK_HEADER.match(line)

                section_header, size1, size2, start1, start2 = extract_hunk_headers(match)

                # check if line range is in this hunk
                if side_lower == 'left':
                    # check if line range is in this hunk
                    if not (start1 <= line_start <= start1 + size1):
                        skip_hunk = True
                        continue
                elif side_lower == 'right':
                    if not (start2 <= line_start <= start2 + size2):
                        skip_hunk = True
                        continue
                patch_with_lines_list.append(f'\n{header_line}\n')

            elif not skip_hunk:
                line_nl = line + '\n'
                if side_lower == 'right' and line_start <= start2 + selected_lines_num <= line_end:
                    selected_lines_list.append(line_nl)
                if side_lower == 'left' and start1 <= selected_lines_num + start1 <= line_end:
                    selected_lines_list.append(line_nl)
                patch_with_lines_list.append(line_nl)
                if not line.startswith('-'): # currently we don't support /ask line for deleted lines
                    selected_lines_num += 1
    except Exception as e:
        get_logger().error(f"Failed to extract hunk lines from patch: {e}", artifact={"traceback": traceback.format_exc()})
        return "", ""

    patch_with_lines_str = "".join(patch_with_lines_list)
    selected_lines = "".join(selected_lines_list)

    if remove_trailing_chars:
        patch_with_lines_str = patch_with_lines_str.rstrip()
        selected_lines = selected_lines.rstrip()

    return patch_with_lines_str, selected_lines
