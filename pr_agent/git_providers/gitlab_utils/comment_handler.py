import difflib
from typing import Optional
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings

class GitLabCommentHandler:
    def __init__(self, provider):
        self.provider = provider
        self.temp_comments = []

    def publish_comment(self, mr_comment: str, is_temporary: bool = False):
        if is_temporary and not get_settings().config.publish_output_progress:
            get_logger().debug(f"Skipping publish_comment for temporary comment: {mr_comment}")
            return None
        mr_comment = self.provider.limit_output_characters(mr_comment, self.provider.max_comment_chars)
        comment = self.provider.mr.notes.create({'body': mr_comment})
        if is_temporary:
            self.temp_comments.append(comment)
        return comment

    def edit_comment(self, comment, body: str):
        body = self.provider.limit_output_characters(body, self.provider.max_comment_chars)
        self.provider.mr.notes.update(comment.id,{'body': body} )

    def edit_comment_from_comment_id(self, comment_id: int, body: str):
        body = self.provider.limit_output_characters(body, self.provider.max_comment_chars)
        comment = self.provider.mr.notes.get(comment_id)
        comment.body = body
        comment.save()

    def reply_to_comment_from_comment_id(self, comment_id: int, body: str):
        body = self.provider.limit_output_characters(body, self.provider.max_comment_chars)
        discussion = self.provider.mr.discussions.get(comment_id)
        discussion.notes.create({'body': body})

    def publish_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, original_suggestion=None):
        body = self.provider.limit_output_characters(body, self.provider.max_comment_chars)
        edit_type, found, source_line_no, target_file, target_line_no = self.provider.search_line(relevant_file,
                                                                                         relevant_line_in_file)
        self.send_inline_comment(body, edit_type, found, relevant_file, relevant_line_in_file, source_line_no,
                                 target_file, target_line_no, original_suggestion)

    def create_inline_comment(self, body: str, relevant_file: str, relevant_line_in_file: str, absolute_position: int = None):
        raise NotImplementedError("Gitlab provider does not support creating inline comments yet")

    def create_inline_comments(self, comments: list[dict]):
        raise NotImplementedError("Gitlab provider does not support publishing inline comments yet")

    def get_comment_body_from_comment_id(self, comment_id: int):
        comment = self.provider.mr.notes.get(comment_id).body
        return comment

    def send_inline_comment(self, body: str, edit_type: str, found: bool, relevant_file: str,
                            relevant_line_in_file: str,
                            source_line_no: int, target_file: str, target_line_no: int,
                            original_suggestion=None) -> None:
        if not found:
            get_logger().info(f"Could not find position for {relevant_file} {relevant_line_in_file}")
        else:
            diff = self.provider.get_relevant_diff(relevant_file, relevant_line_in_file)
            if diff is None:
                get_logger().error(f"Could not get diff for merge request {self.provider.id_mr}")
                raise ValueError(f"Could not get diff for merge request {self.provider.id_mr}")

            pos_obj = {'position_type': 'text',
                       'new_path': target_file.filename,
                       'old_path': target_file.old_filename if target_file.old_filename else target_file.filename,
                       'base_sha': diff.base_commit_sha, 'start_sha': diff.start_commit_sha, 'head_sha': diff.head_commit_sha}
            if edit_type == 'deletion':
                pos_obj['old_line'] = source_line_no - 1
            elif edit_type == 'addition':
                pos_obj['new_line'] = target_line_no - 1
            else:
                pos_obj['new_line'] = target_line_no - 1
                pos_obj['old_line'] = source_line_no - 1

            try:
                self.provider.mr.discussions.create({'body': body, 'position': pos_obj})
            except Exception as e:
                try:
                    if original_suggestion and 'suggestion_orig_location' in original_suggestion:
                        line_start = original_suggestion['suggestion_orig_location']['start_line']
                        line_end = original_suggestion['suggestion_orig_location']['end_line']
                        old_code_snippet = original_suggestion['prev_code_snippet']
                        new_code_snippet = original_suggestion['new_code_snippet']
                        content = original_suggestion['suggestion_summary']
                        label = original_suggestion['category']
                        score = original_suggestion.get('score', 7)
                    elif original_suggestion:
                        line_start = original_suggestion['relevant_lines_start']
                        line_end = original_suggestion['relevant_lines_end']
                        old_code_snippet = original_suggestion['existing_code']
                        new_code_snippet = original_suggestion['improved_code']
                        content = original_suggestion['suggestion_content']
                        label = original_suggestion['label']
                        score = original_suggestion.get('score', 7)
                    else:
                         get_logger().warning(f"Failed to create inline comment and no suggestion info for fallback: {e}")
                         return

                    link = self.provider.get_line_link(relevant_file, line_start, line_end)
                    body_fallback =f"**Suggestion:** {content} [{label}, importance: {score}]\n\n"
                    body_fallback +=f"\n\n<details><summary>[{target_file.filename} [{line_start}-{line_end}]]({link}):</summary>\n\n"
                    body_fallback += f"\n\n___\n\n`(Cannot implement directly - GitLab API allows committable suggestions strictly on MR diff lines)`"
                    body_fallback+="</details>\n\n"
                    diff_patch = difflib.unified_diff(old_code_snippet.split('\n'),
                                                new_code_snippet.split('\n'), n=999)
                    patch_orig = "\n".join(diff_patch)
                    patch = "\n".join(patch_orig.splitlines()[5:]).strip('\n')
                    diff_code = f"\n\n```diff\n{patch.rstrip()}\n```"
                    body_fallback += diff_code

                    self.provider.mr.notes.create({
                        'body': body_fallback,
                        'position': {
                            'base_sha': diff.base_commit_sha,
                            'start_sha': diff.start_commit_sha,
                            'head_sha': diff.head_commit_sha,
                            'position_type': 'text',
                            'file_path': f'{target_file.filename}',
                        }
                    })
                except Exception as e:
                    get_logger().exception(f"Failed to create comment in MR {self.provider.id_mr}")

    def publish_code_suggestions(self, code_suggestions: list) -> bool:
        for suggestion in code_suggestions:
            try:
                if suggestion and 'original_suggestion' in suggestion:
                    original_suggestion = suggestion['original_suggestion']
                else:
                    original_suggestion = suggestion
                body = suggestion['body']
                relevant_file = suggestion['relevant_file']
                relevant_lines_start = suggestion['relevant_lines_start']
                relevant_lines_end = suggestion['relevant_lines_end']

                diff_files = self.provider.get_diff_files()
                target_file = None
                for file in diff_files:
                    if file.filename == relevant_file:
                        target_file = file
                        break

                if not target_file:
                    continue

                range_len = relevant_lines_end - relevant_lines_start
                body = body.replace('```suggestion', f'```suggestion:-0+{range_len}')
                lines = target_file.head_file.splitlines()
                if relevant_lines_start - 1 < len(lines):
                    relevant_line_in_file = lines[relevant_lines_start - 1]
                else:
                     continue

                source_line_no = -1
                target_line_no = relevant_lines_start + 1
                found = True
                edit_type = 'addition'

                self.send_inline_comment(body, edit_type, found, relevant_file, relevant_line_in_file, source_line_no,
                                         target_file, target_line_no, original_suggestion)
            except Exception as e:
                get_logger().exception(f"Could not publish code suggestion:\nsuggestion: {suggestion}\nerror: {e}")
        return True

    def publish_file_comments(self, file_comments: list) -> bool:
        pass

    def remove_initial_comment(self):
        try:
            for comment in self.temp_comments:
                self.remove_comment(comment)
        except Exception as e:
            get_logger().exception(f"Failed to remove temp comments, error: {e}")

    def remove_comment(self, comment):
        try:
            comment.delete()
        except Exception as e:
            get_logger().exception(f"Failed to remove comment, error: {e}")
