from __future__ import annotations

import re

from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

RE_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[ ]?(.*)")


class PatchProcessor:
    def __init__(self, patch_str, original_file_str, patch_extra_lines_before, patch_extra_lines_after, new_file_str=""):
        self.patch_str = patch_str
        self.original_file_str = original_file_str
        self.patch_extra_lines_before = patch_extra_lines_before
        self.patch_extra_lines_after = patch_extra_lines_after
        self.new_file_str = new_file_str

        self.file_original_lines = original_file_str.splitlines()
        self.file_new_lines = new_file_str.splitlines() if new_file_str else []
        self.len_original_lines = len(self.file_original_lines)
        self.patch_lines = patch_str.splitlines()
        self.extended_patch_lines = []

        self.is_valid_hunk = True
        self.start1 = -1
        self.size1 = -1
        self.start2 = -1
        self.size2 = -1
        self.section_header = ""

        self.allow_dynamic_context = get_settings().config.allow_dynamic_context
        self.patch_extra_lines_before_dynamic = get_settings().config.max_extra_lines_before_dynamic_context
        self.RE_HUNK_HEADER = RE_HUNK_HEADER
        self.detected_encoding = None

    def process(self) -> str:
        for i, line in enumerate(self.patch_lines):
            if line.startswith('@@'):
                match = self.RE_HUNK_HEADER.match(line)
                if match:
                    self._finish_previous_hunk()
                    self.section_header, self.size1, self.size2, self.start1, self.start2 = extract_hunk_headers(match)
                    self.is_valid_hunk = self._check_if_hunk_lines_matches_to_file(i, self.start1)

                    if self.is_valid_hunk and (self.patch_extra_lines_before > 0 or self.patch_extra_lines_after > 0):
                        self._extend_hunk()
                    else:
                        self._reset_extension_vars()
                        self.extended_patch_lines.append(line) # append the original hunk header
                    continue
            self.extended_patch_lines.append(line)

        self._finish_last_hunk()
        return '\n'.join(self.extended_patch_lines)

    def _finish_previous_hunk(self):
        if self.is_valid_hunk and (self.start1 != -1 and self.patch_extra_lines_after > 0):
            delta_lines_original = [f' {line}' for line in self.file_original_lines[self.start1 + self.size1 - 1:self.start1 + self.size1 - 1 + self.patch_extra_lines_after]]
            self.extended_patch_lines.extend(delta_lines_original)

    def _finish_last_hunk(self):
        if self.start1 != -1 and self.patch_extra_lines_after > 0 and self.is_valid_hunk:
            delta_lines_original = self.file_original_lines[self.start1 + self.size1 - 1:self.start1 + self.size1 - 1 + self.patch_extra_lines_after]
            delta_lines_original = [f' {line}' for line in delta_lines_original]
            self.extended_patch_lines.extend(delta_lines_original)

    def _reset_extension_vars(self):
        # Just setting placeholders for next calculations if needed, but mainly we just append the line in the loop
        pass

    def _calc_context_limits(self, patch_lines_before):
        extended_start1 = max(1, self.start1 - patch_lines_before)
        extended_size1 = self.size1 + (self.start1 - extended_start1) + self.patch_extra_lines_after
        extended_start2 = max(1, self.start2 - patch_lines_before)
        extended_size2 = self.size2 + (self.start2 - extended_start2) + self.patch_extra_lines_after
        if extended_start1 - 1 + extended_size1 > self.len_original_lines:
            # we cannot extend beyond the original file
            delta_cap = extended_start1 - 1 + extended_size1 - self.len_original_lines
            extended_size1 = max(extended_size1 - delta_cap, self.size1)
            extended_size2 = max(extended_size2 - delta_cap, self.size2)
        return extended_start1, extended_size1, extended_start2, extended_size2

    def _extend_hunk(self):
        if self.allow_dynamic_context and self.file_new_lines:
            extended_start1, extended_size1, extended_start2, extended_size2 = \
                self._calc_context_limits(self.patch_extra_lines_before_dynamic)

            lines_before_original = self.file_original_lines[extended_start1 - 1:self.start1 - 1]
            lines_before_new = self.file_new_lines[extended_start2 - 1:self.start2 - 1]
            found_header = False
            for i, line in enumerate(lines_before_original):
                if self.section_header in line:
                    # Update start and size in one line each
                    extended_start1, extended_start2 = extended_start1 + i, extended_start2 + i
                    extended_size1, extended_size2 = extended_size1 - i, extended_size2 - i
                    lines_before_original_dynamic_context = lines_before_original[i:]
                    lines_before_new_dynamic_context = lines_before_new[i:]
                    if lines_before_original_dynamic_context == lines_before_new_dynamic_context:
                        found_header = True
                        self.section_header = ''
                    break

            if not found_header:
                extended_start1, extended_size1, extended_start2, extended_size2 = \
                    self._calc_context_limits(self.patch_extra_lines_before)
        else:
            extended_start1, extended_size1, extended_start2, extended_size2 = \
                self._calc_context_limits(self.patch_extra_lines_before)

        # check if extra lines before hunk are different in original and new file
        delta_lines_original = [f' {line}' for line in self.file_original_lines[extended_start1 - 1:self.start1 - 1]]
        if self.file_new_lines:
            delta_lines_new = [f' {line}' for line in self.file_new_lines[extended_start2 - 1:self.start2 - 1]]
            if delta_lines_original != delta_lines_new:
                found_mini_match = False
                for i in range(len(delta_lines_original)):
                    if delta_lines_original[i:] == delta_lines_new[i:]:
                        delta_lines_original = delta_lines_original[i:]
                        # delta_lines_new = delta_lines_new[i:] # unused
                        extended_start1 += i
                        extended_size1 -= i
                        extended_start2 += i
                        extended_size2 -= i
                        found_mini_match = True
                        break
                if not found_mini_match:
                    extended_start1 = self.start1
                    extended_size1 = self.size1
                    extended_start2 = self.start2
                    extended_size2 = self.size2
                    delta_lines_original = []

        #  logic to remove section header if its in the extra delta lines (in dynamic context, this is also done)
        if self.section_header and not self.allow_dynamic_context:
            for line in delta_lines_original:
                if self.section_header in line:
                    self.section_header = ''  # remove section header if it is in the extra delta lines
                    break

        self.extended_patch_lines.append('')
        self.extended_patch_lines.append(
            f'@@ -{extended_start1},{extended_size1} '
            f'+{extended_start2},{extended_size2} @@ {self.section_header}')
        self.extended_patch_lines.extend(delta_lines_original)

    def _check_if_hunk_lines_matches_to_file(self, i, start1):
        """
        Check if the hunk lines match the original file content.
        """
        is_valid_hunk = True
        try:
            if i + 1 < len(self.patch_lines) and self.patch_lines[i + 1][0] == ' ': # an existing line in the file
                patch_line_stripped = self.patch_lines[i + 1].strip()
                original_line_stripped = self.file_original_lines[start1 - 1].strip()

                if patch_line_stripped != original_line_stripped:
                    # check if different encoding is needed
                    original_line = self.file_original_lines[start1 - 1].strip()

                    # Try cached encoding first
                    if self.detected_encoding:
                        try:
                            if original_line.encode(self.detected_encoding).decode().strip() == patch_line_stripped:
                                return False # Avoid extending, treat as invalid for extension but suppress error
                        except:
                            pass

                    # Try other encodings
                    encodings_to_try = ['iso-8859-1', 'latin-1', 'ascii', 'utf-16']
                    for encoding in encodings_to_try:
                        if encoding == self.detected_encoding:
                            continue
                        try:
                            if original_line.encode(encoding).decode().strip() == patch_line_stripped:
                                get_logger().info(f"Detected different encoding in hunk header line {start1}, needed encoding: {encoding}")
                                self.detected_encoding = encoding
                                return False
                        except:
                            pass

                    is_valid_hunk = False
                    get_logger().info(
                        f"Invalid hunk in PR, line {start1} in hunk header doesn't match the original file content")
        except:
            is_valid_hunk = False
        return is_valid_hunk


def check_if_hunk_lines_matches_to_file(i, original_lines, patch_lines, start1):
    """
    Check if the hunk lines match the original file content. We saw cases where the hunk header line doesn't match the original file content, and then
    extending the hunk with extra lines before the hunk header can cause the hunk to be invalid.
    """
    is_valid_hunk = True
    try:
        if i + 1 < len(patch_lines) and patch_lines[i + 1][0] == ' ': # an existing line in the file
            if patch_lines[i + 1].strip() != original_lines[start1 - 1].strip():
                # check if different encoding is needed
                original_line = original_lines[start1 - 1].strip()
                for encoding in ['iso-8859-1', 'latin-1', 'ascii', 'utf-16']:
                    try:
                        if original_line.encode(encoding).decode().strip() == patch_lines[i + 1].strip():
                            get_logger().info(f"Detected different encoding in hunk header line {start1}, needed encoding: {encoding}")
                            return False # we still want to avoid extending the hunk. But we don't want to log an error
                    except:
                        pass

                is_valid_hunk = False
                get_logger().info(
                    f"Invalid hunk in PR, line {start1} in hunk header doesn't match the original file content")
    except:
        is_valid_hunk = False
    return is_valid_hunk


def extract_hunk_headers(match):
    res = list(match.groups())
    for i in range(len(res)):
        if res[i] is None:
            res[i] = 0
    try:
        start1, size1, start2, size2 = map(int, res[:4])
    except:  # '@@ -0,0 +1 @@' case
        start1, size1, size2 = map(int, res[:3])
        start2 = 0
    section_header = res[4]
    return section_header, size1, size2, start1, start2
