import re
from typing import Optional
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.file_filter import filter_ignored
from pr_agent.algo.language_handler import is_valid_file
from pr_agent.algo.types import EDIT_TYPE
from pr_agent.algo.utils import load_large_diff
from pr_agent.git_providers.git_provider import MAX_FILES_ALLOWED_FULL, FilePatchInfo

def decode_if_bytes(content):
    if isinstance(content, bytes):
        return content.decode('utf-8')
    return content

class GitLabDiffHandler:
    def __init__(self, provider):
        self.provider = provider
        self.RE_HUNK_HEADER = re.compile(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[ ]?(.*)")

    def get_diff_files(self) -> list[FilePatchInfo]:
        if self.provider.diff_files:
            return self.provider.diff_files

        # filter files using [ignore] patterns
        raw_changes = self.provider.mr.changes().get('changes', [])
        # We need to access submodule handler here or in provider.
        # Assuming provider has submodule_handler or delegates.
        raw_changes = self.provider.expand_submodule_changes(raw_changes)

        diffs_original = raw_changes
        diffs = filter_ignored(diffs_original, 'gitlab')
        if diffs != diffs_original:
            try:
                names_original = [diff['new_path'] for diff in diffs_original]
                names_filtered = [diff['new_path'] for diff in diffs]
                get_logger().info(f"Filtered out [ignore] files for merge request {self.provider.id_mr}", extra={
                    'original_files': names_original,
                    'filtered_files': names_filtered
                })
            except Exception as e:
                pass

        diff_files = []
        invalid_files_names = []
        counter_valid = 0
        for diff in diffs:
            if not is_valid_file(diff['new_path']):
                invalid_files_names.append(diff['new_path'])
                continue

            counter_valid += 1
            max_files_allowed = MAX_FILES_ALLOWED_FULL
            if get_settings().config.get("token_economy_mode", False):
                max_files_allowed = get_settings().config.get("max_files_in_economy_mode", 6)
                if counter_valid == 1:
                    get_logger().info(f"Token economy mode enabled. Limiting files to {max_files_allowed}")

            if counter_valid <= max_files_allowed or not diff['diff']:
                original_file_content_str = self.provider.get_pr_file_content(diff['old_path'], self.provider.mr.diff_refs['base_sha'])
                new_file_content_str = self.provider.get_pr_file_content(diff['new_path'], self.provider.mr.diff_refs['head_sha'])
            else:
                if counter_valid == max_files_allowed:
                    get_logger().info(f"Too many files in PR, will avoid loading full content for rest of files")
                original_file_content_str = ''
                new_file_content_str = ''

            original_file_content_str = decode_if_bytes(original_file_content_str)
            new_file_content_str = decode_if_bytes(new_file_content_str)

            edit_type = EDIT_TYPE.MODIFIED
            if diff['new_file']:
                edit_type = EDIT_TYPE.ADDED
            elif diff['deleted_file']:
                edit_type = EDIT_TYPE.DELETED
            elif diff['renamed_file']:
                edit_type = EDIT_TYPE.RENAMED

            filename = diff['new_path']
            patch = diff['diff']
            if not patch:
                patch = load_large_diff(filename, new_file_content_str, original_file_content_str)

            patch_lines = patch.splitlines(keepends=True)
            num_plus_lines = len([line for line in patch_lines if line.startswith('+')])
            num_minus_lines = len([line for line in patch_lines if line.startswith('-')])
            diff_files.append(
                FilePatchInfo(original_file_content_str, new_file_content_str,
                              patch=patch,
                              filename=filename,
                              edit_type=edit_type,
                              old_filename=None if diff['old_path'] == diff['new_path'] else diff['old_path'],
                              num_plus_lines=num_plus_lines,
                              num_minus_lines=num_minus_lines, ))
        if invalid_files_names:
            get_logger().info(f"Filtered out files with invalid extensions: {invalid_files_names}")

        self.provider.diff_files = diff_files
        return diff_files

    def get_files(self) -> list:
        if not self.provider.git_files:
            raw_changes = self.provider.mr.changes().get('changes', [])
            raw_changes = self.provider.expand_submodule_changes(raw_changes)
            self.provider.git_files = [c.get('new_path') for c in raw_changes if c.get('new_path')]
        return self.provider.git_files

    def get_relevant_diff(self, relevant_file: str, relevant_line_in_file: str) -> Optional[dict]:
        _changes = self.provider.mr.changes()
        _changes['changes'] = self.provider.expand_submodule_changes(_changes.get('changes', []))
        changes = _changes
        if not changes:
            get_logger().error('No changes found for the merge request.')
            return None
        all_diffs = self.provider.mr.diffs.list(get_all=True)
        if not all_diffs:
            get_logger().error('No diffs found for the merge request.')
            return None
        for diff in all_diffs:
            for change in changes['changes']:
                if change['new_path'] == relevant_file and relevant_line_in_file in change['diff']:
                    return diff
            get_logger().debug(
                f'No relevant diff found for {relevant_file} {relevant_line_in_file}. Falling back to last diff.')
        return self.provider.last_diff

    def search_line(self, relevant_file, relevant_line_in_file):
        target_file = None

        edit_type = self.get_edit_type(relevant_line_in_file)
        for file in self.get_diff_files():
            if file.filename == relevant_file:
                edit_type, found, source_line_no, target_file, target_line_no = self.find_in_file(file,
                                                                                                  relevant_line_in_file)
        return edit_type, found, source_line_no, target_file, target_line_no

    def find_in_file(self, file, relevant_line_in_file):
        edit_type = 'context'
        source_line_no = 0
        target_line_no = 0
        found = False
        target_file = file
        patch = file.patch
        patch_lines = patch.splitlines()
        for line in patch_lines:
            if line.startswith('@@'):
                match = self.RE_HUNK_HEADER.match(line)
                if not match:
                    continue
                start_old, size_old, start_new, size_new, _ = match.groups()
                source_line_no = int(start_old)
                target_line_no = int(start_new)
                continue
            if line.startswith('-'):
                source_line_no += 1
            elif line.startswith('+'):
                target_line_no += 1
            elif line.startswith(' '):
                source_line_no += 1
                target_line_no += 1
            if relevant_line_in_file in line:
                found = True
                edit_type = self.get_edit_type(line)
                break
            elif relevant_line_in_file[0] == '+' and relevant_line_in_file[1:].lstrip() in line:
                found = True
                edit_type = self.get_edit_type(line)
                break
        return edit_type, found, source_line_no, target_file, target_line_no

    def get_edit_type(self, relevant_line_in_file):
        edit_type = 'context'
        if relevant_line_in_file[0] == '-':
            edit_type = 'deletion'
        elif relevant_line_in_file[0] == '+':
            edit_type = 'addition'
        return edit_type
