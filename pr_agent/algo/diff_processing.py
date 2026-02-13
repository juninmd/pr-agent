from __future__ import annotations

import traceback
from typing import List, Tuple

from pr_agent.algo.git_patch_processing import (
    decouple_and_convert_to_hunks_with_lines_numbers, extend_patch,
    handle_patch_deletions)
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.algo.types import EDIT_TYPE
from pr_agent.algo.utils import clip_tokens, get_max_tokens
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

DELETED_FILES_ = "Deleted files:\n"
MORE_MODIFIED_FILES_ = "Additional modified files (insufficient token budget to process):\n"
ADDED_FILES_ = "Additional added files (insufficient token budget to process):\n"
OUTPUT_BUFFER_TOKENS_SOFT_THRESHOLD = 1500
OUTPUT_BUFFER_TOKENS_HARD_THRESHOLD = 1000
MAX_EXTRA_LINES = 10


def pr_generate_extended_diff(pr_languages: list,
                              token_handler: TokenHandler,
                              add_line_numbers_to_hunks: bool,
                              patch_extra_lines_before: int = 0,
                              patch_extra_lines_after: int = 0) -> Tuple[list, int, list]:
    total_tokens = token_handler.prompt_tokens  # initial tokens
    patches_extended = []
    patches_extended_tokens = []
    enable_ai_metadata = get_settings().get("config.enable_ai_metadata", False)

    for lang in pr_languages:
        for file in lang['files']:
            original_file_content_str = file.base_file
            new_file_content_str = file.head_file
            patch = file.patch
            if not patch:
                continue

            # extend each patch with extra lines of context
            extended_patch = extend_patch(original_file_content_str, patch,
                                          patch_extra_lines_before, patch_extra_lines_after, file.filename,
                                          new_file_str=new_file_content_str)
            if not extended_patch:
                get_logger().warning(f"Failed to extend patch for file: {file.filename}")
                continue

            if add_line_numbers_to_hunks:
                full_extended_patch = decouple_and_convert_to_hunks_with_lines_numbers(extended_patch, file)
            else:
                extended_patch = extended_patch.replace('\n@@ ', '\n\n@@ ') # add extra line before each hunk
                full_extended_patch = f"\n\n## File: '{file.filename.strip()}'\n\n{extended_patch.strip()}\n"

            # add AI-summary metadata to the patch
            if file.ai_file_summary and enable_ai_metadata:
                full_extended_patch = add_ai_summary_top_patch(file, full_extended_patch)

            patch_tokens = token_handler.count_tokens(full_extended_patch)
            file.tokens = patch_tokens
            total_tokens += patch_tokens
            patches_extended_tokens.append(patch_tokens)
            patches_extended.append(full_extended_patch)

    return patches_extended, total_tokens, patches_extended_tokens


def pr_generate_compressed_diff(top_langs: list, token_handler: TokenHandler, model: str,
                                convert_hunks_to_line_numbers: bool,
                                large_pr_handling: bool) -> Tuple[list, list, list, list, dict, list]:
    deleted_files_list = []

    # sort each one of the languages in top_langs by the number of tokens in the diff
    sorted_files = []
    for lang in top_langs:
        sorted_files.extend(sorted(lang['files'], key=lambda x: x.tokens, reverse=True))

    # generate patches for each file, and count tokens
    file_dict = {}
    for file in sorted_files:
        original_file_content_str = file.base_file
        new_file_content_str = file.head_file
        patch = file.patch
        if not patch:
            continue

        # removing delete-only hunks
        patch = handle_patch_deletions(patch, original_file_content_str,
                                       new_file_content_str, file.filename, file.edit_type)
        if patch is None:
            if file.filename not in deleted_files_list:
                deleted_files_list.append(file.filename)
            continue

        if convert_hunks_to_line_numbers:
            patch = decouple_and_convert_to_hunks_with_lines_numbers(patch, file)

        ## add AI-summary metadata to the patch (disabled, since we are in the compressed diff)
        # if file.ai_file_summary and get_settings().config.get('config.is_auto_command', False):
        #     patch = add_ai_summary_top_patch(file, patch)

        new_patch_tokens = token_handler.count_tokens(patch)
        file_dict[file.filename] = {'patch': patch, 'tokens': new_patch_tokens, 'edit_type': file.edit_type}

    max_tokens_model = get_max_tokens(model)

    # first iteration
    files_in_patches_list = []
    remaining_files_list =  [file.filename for file in sorted_files]
    patches_list =[]
    total_tokens_list = []
    total_tokens, patches, remaining_files_list, files_in_patch_list = generate_full_patch(convert_hunks_to_line_numbers, file_dict,
                                       max_tokens_model, remaining_files_list, token_handler)
    patches_list.append(patches)
    total_tokens_list.append(total_tokens)
    files_in_patches_list.append(files_in_patch_list)

    # additional iterations (if needed)
    if large_pr_handling:
        NUMBER_OF_ALLOWED_ITERATIONS = get_settings().pr_description.max_ai_calls - 1 # one more call is to summarize
        for i in range(NUMBER_OF_ALLOWED_ITERATIONS-1):
            if remaining_files_list:
                total_tokens, patches, remaining_files_list, files_in_patch_list = generate_full_patch(convert_hunks_to_line_numbers,
                                                                                 file_dict,
                                                                                  max_tokens_model,
                                                                                  remaining_files_list, token_handler)
                if patches:
                    patches_list.append(patches)
                    total_tokens_list.append(total_tokens)
                    files_in_patches_list.append(files_in_patch_list)
            else:
                break

    return patches_list, total_tokens_list, deleted_files_list, remaining_files_list, file_dict, files_in_patches_list


def generate_full_patch(convert_hunks_to_line_numbers, file_dict, max_tokens_model,remaining_files_list_prev, token_handler):
    total_tokens = token_handler.prompt_tokens # initial tokens
    patches = []
    remaining_files_list_new = []
    files_in_patch_list = []

    # Pre-calculated header tokens
    new_line_tokens = token_handler.count_tokens("\n\n")

    verbosity_level = get_settings().config.verbosity_level

    for filename in remaining_files_list_prev:
        data = file_dict.get(filename)
        if not data:
            continue

        patch = data['patch']
        new_patch_tokens = data['tokens']
        edit_type = data['edit_type']

        # Hard Stop, no more tokens
        if total_tokens > max_tokens_model - OUTPUT_BUFFER_TOKENS_HARD_THRESHOLD:
            get_logger().warning(f"File was fully skipped, no more tokens: {filename}.")
            continue

        # If the patch is too large, just show the file name
        if total_tokens + new_patch_tokens > max_tokens_model - OUTPUT_BUFFER_TOKENS_SOFT_THRESHOLD:
            # Current logic is to skip the patch if it's too large
            # TODO: Option for alternative logic to remove hunks from the patch to reduce the number of tokens
            #  until we meet the requirements
            if verbosity_level >= 2:
                get_logger().warning(f"Patch too large, skipping it: '{filename}'")
            remaining_files_list_new.append(filename)
            continue

        if patch:
            if not convert_hunks_to_line_numbers:
                header = f"\n\n## File: '{filename.strip()}'\n\n"
                patch_final = f"{header}{patch.strip()}\n"

                # Use approximate token counting for performance (avoid re-tokenizing the whole patch)
                # The token count of the header + patch is close enough to the sum of token counts
                header_tokens = token_handler.count_tokens(header)
                current_tokens = header_tokens + new_patch_tokens
                total_tokens += current_tokens
            else:
                patch_final = "\n\n" + patch.strip()

                # Use approximate token counting for performance
                current_tokens = new_line_tokens + new_patch_tokens
                total_tokens += current_tokens

            patches.append(patch_final)
            files_in_patch_list.append(filename)
            if verbosity_level >= 2:
                get_logger().info(f"Tokens: {total_tokens}, last filename: {filename}")
    return total_tokens, patches, remaining_files_list_new, files_in_patch_list


def add_ai_summary_top_patch(file, full_extended_patch):
    try:
        # below every instance of '## File: ...' in the patch, add the ai-summary metadata
        # Optimized to avoid splitting the whole file
        current_pos = 0
        while True:
            next_newline = full_extended_patch.find('\n', current_pos)
            if next_newline == -1:
                if full_extended_patch.startswith("## File:", current_pos) or \
                        full_extended_patch.startswith("## file:", current_pos):
                    # Insert after this line (which is end of string)
                    to_insert = f"\n### AI-generated changes summary:\n{file.ai_file_summary['long_summary']}"
                    return full_extended_patch + to_insert
                break

            if full_extended_patch.startswith("## File:", current_pos) or \
                    full_extended_patch.startswith("## file:", current_pos):
                # Insert after next_newline
                to_insert = f"\n### AI-generated changes summary:\n{file.ai_file_summary['long_summary']}"
                return full_extended_patch[:next_newline] + to_insert + full_extended_patch[next_newline:]

            current_pos = next_newline + 1
            if current_pos >= len(full_extended_patch):
                break

        # if no '## File: ...' was found
        return full_extended_patch
    except Exception as e:
        get_logger().error(f"Failed to add AI summary to the top of the patch: {e}",
                           artifact={"traceback": traceback.format_exc()})
        return full_extended_patch
