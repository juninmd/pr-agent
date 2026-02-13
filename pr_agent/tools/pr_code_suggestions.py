import traceback
from functools import partial
from typing import Dict

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.pr_processing import (add_ai_metadata_to_diff_files)
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.algo.utils import load_yaml
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.algo.language_handler import get_main_pr_language
from pr_agent.log import get_logger
from pr_agent.tools.pr_code_suggestions_utils.helpers import (
    dedent_code, truncate_if_needed
)
from pr_agent.tools.pr_code_suggestions_utils.prediction_handler import PredictionHandler
from pr_agent.tools.pr_code_suggestions_utils.reflection_handler import ReflectionHandler
from pr_agent.tools.pr_code_suggestions_utils.runner import SuggestionRunner
from datetime import datetime

class PRCodeSuggestions:
    def __init__(self, pr_url: str, cli_mode=False, args: list = None,
                 ai_handler: partial[BaseAiHandler,] = LiteLLMAIHandler):

        self.git_provider = get_git_provider_with_context(pr_url)
        self.main_language = get_main_pr_language(
            self.git_provider.get_languages(), self.git_provider.get_files()
        )

        num_code_suggestions = int(get_settings().pr_code_suggestions.num_code_suggestions_per_chunk)

        self.ai_handler = ai_handler()
        self.ai_handler.main_pr_language = self.main_language
        self.patches_diff = None
        self.prediction = None
        self.pr_url = pr_url
        self.cli_mode = cli_mode
        self.pr_description, self.pr_description_files = (
            self.git_provider.get_pr_description(split_changes_walkthrough=True))
        if (self.pr_description_files and get_settings().get("config.is_auto_command", False) and
                get_settings().get("config.enable_ai_metadata", False)):
            add_ai_metadata_to_diff_files(self.git_provider, self.pr_description_files)
            get_logger().debug(f"AI metadata added to the this command")
        else:
            get_settings().set("config.enable_ai_metadata", False)
            get_logger().debug(f"AI metadata is disabled for this command")

        self.vars = {
            "title": self.git_provider.pr.title,
            "branch": self.git_provider.get_pr_branch(),
            "description": self.pr_description,
            "language": self.main_language,
            "diff": "",  # empty diff for initial calculation
            "diff_no_line_numbers": "",  # empty diff for initial calculation
            "num_code_suggestions": num_code_suggestions,
            "extra_instructions": get_settings().pr_code_suggestions.extra_instructions,
            "commit_messages_str": self.git_provider.get_commit_messages(),
            "relevant_best_practices": "",
            "is_ai_metadata": get_settings().get("config.enable_ai_metadata", False),
            "focus_only_on_problems": get_settings().get("pr_code_suggestions.focus_only_on_problems", False),
            "date": datetime.now().strftime('%Y-%m-%d'),
            'duplicate_prompt_examples': get_settings().config.get('duplicate_prompt_examples', False),
        }

        if get_settings().pr_code_suggestions.get("decouple_hunks", True):
            self.pr_code_suggestions_prompt_system = get_settings().pr_code_suggestions_prompt.system
            self.pr_code_suggestions_prompt_user = get_settings().pr_code_suggestions_prompt.user
        else:
            self.pr_code_suggestions_prompt_system = get_settings().pr_code_suggestions_prompt_not_decoupled.system
            self.pr_code_suggestions_prompt_user = get_settings().pr_code_suggestions_prompt_not_decoupled.user

        self.token_handler = TokenHandler(self.git_provider.pr,
                                          self.vars,
                                          self.pr_code_suggestions_prompt_system,
                                          self.pr_code_suggestions_prompt_user)

        self.progress = f"## Generating PR code suggestions\n\n"
        self.progress += f"""\nWork in progress ...<br>\n<img src="https://codium.ai/images/pr_agent/dual_ball_loading-crop.gif" width=48>"""
        self.progress_response = None
        self.prediction_handler = PredictionHandler(self)
        self.reflection_handler = ReflectionHandler(self)
        self.runner = SuggestionRunner(self)

    async def run(self):
        await self.runner.run()

    async def publish_no_suggestions(self):
        pr_body = "## PR Code Suggestions ✨\n\nNo code suggestions found for the PR."
        if (get_settings().config.publish_output and
                get_settings().pr_code_suggestions.get('publish_output_no_suggestions', True)):
            get_logger().warning('No code suggestions found for the PR.')
            get_logger().debug(f"PR output", artifact=pr_body)
            if self.progress_response:
                self.git_provider.edit_comment(self.progress_response, body=pr_body)
            else:
                self.git_provider.publish_comment(pr_body)
        else:
            get_settings().data = {"artifact": ""}

    async def dual_publishing(self, data):
        data_above_threshold = {'code_suggestions': []}
        try:
            for suggestion in data['code_suggestions']:
                if int(suggestion.get('score', 0)) >= int(
                        get_settings().pr_code_suggestions.dual_publishing_score_threshold) \
                        and suggestion.get('improved_code'):
                    data_above_threshold['code_suggestions'].append(suggestion)
                    if not data_above_threshold['code_suggestions'][-1]['existing_code']:
                        get_logger().info(f'Identical existing and improved code for dual publishing found')
                        data_above_threshold['code_suggestions'][-1]['existing_code'] = suggestion[
                            'improved_code']
            if data_above_threshold['code_suggestions']:
                get_logger().info(
                    f"Publishing {len(data_above_threshold['code_suggestions'])} suggestions in dual publishing mode")
                await self.push_inline_code_suggestions(data_above_threshold)
        except Exception as e:
            get_logger().error(f"Failed to publish dual publishing suggestions, error: {e}")

    def _prepare_pr_code_suggestions(self, predictions: str) -> Dict:
        data = load_yaml(predictions.strip(),
                         keys_fix_yaml=["relevant_file", "suggestion_content", "existing_code", "improved_code"],
                         first_key="code_suggestions", last_key="label")
        if isinstance(data, list):
            data = {'code_suggestions': data}

        # remove or edit invalid suggestions
        suggestion_list = []
        one_sentence_summary_list = []
        for i, suggestion in enumerate(data['code_suggestions']):
            try:
                needed_keys = ['one_sentence_summary', 'label', 'relevant_file']
                is_valid_keys = True
                for key in needed_keys:
                    if key not in suggestion:
                        is_valid_keys = False
                        get_logger().debug(
                            f"Skipping suggestion {i + 1}, because it does not contain '{key}':\n'{suggestion}")
                        break
                if not is_valid_keys:
                    continue

                if get_settings().get("pr_code_suggestions.focus_only_on_problems", False):
                    CRITICAL_LABEL = 'critical'
                    if CRITICAL_LABEL in suggestion['label'].lower(): # we want the published labels to be less declarative
                        suggestion['label'] = 'possible issue'

                if suggestion['one_sentence_summary'] in one_sentence_summary_list:
                    get_logger().debug(f"Skipping suggestion {i + 1}, because it is a duplicate: {suggestion}")
                    continue

                if 'const' in suggestion['suggestion_content'] and 'instead' in suggestion[
                    'suggestion_content'] and 'let' in suggestion['suggestion_content']:
                    get_logger().debug(
                        f"Skipping suggestion {i + 1}, because it uses 'const instead let': {suggestion}")
                    continue

                if ('existing_code' in suggestion) and ('improved_code' in suggestion):
                    suggestion = truncate_if_needed(suggestion)
                    one_sentence_summary_list.append(suggestion['one_sentence_summary'])
                    suggestion_list.append(suggestion)
                else:
                    get_logger().info(
                        f"Skipping suggestion {i + 1}, because it does not contain 'existing_code' or 'improved_code': {suggestion}")
            except Exception as e:
                get_logger().error(f"Error processing suggestion {i + 1}: {suggestion}, error: {e}")
        data['code_suggestions'] = suggestion_list

        return data

    async def push_inline_code_suggestions(self, data):
        code_suggestions = []

        if not data['code_suggestions']:
            get_logger().info('No suggestions found to improve this PR.')
            if self.progress_response:
                return self.git_provider.edit_comment(self.progress_response,
                                                      body='No suggestions found to improve this PR.')
            else:
                return self.git_provider.publish_comment('No suggestions found to improve this PR.')

        for d in data['code_suggestions']:
            try:
                if get_settings().config.verbosity_level >= 2:
                    get_logger().info(f"suggestion: {d}")
                relevant_file = d['relevant_file'].strip()
                relevant_lines_start = int(d['relevant_lines_start'])  # absolute position
                relevant_lines_end = int(d['relevant_lines_end'])
                content = d['suggestion_content'].rstrip()
                new_code_snippet = d['improved_code'].rstrip()
                label = d['label'].strip()

                if new_code_snippet:
                    new_code_snippet = dedent_code(relevant_file, relevant_lines_start, new_code_snippet, self.git_provider)

                if d.get('score'):
                    body = f"**Suggestion:** {content} [{label}, importance: {d.get('score')}]\n```suggestion\n" + new_code_snippet + "\n```"
                else:
                    body = f"**Suggestion:** {content} [{label}]\n```suggestion\n" + new_code_snippet + "\n```"
                code_suggestions.append({'body': body, 'relevant_file': relevant_file,
                                         'relevant_lines_start': relevant_lines_start,
                                         'relevant_lines_end': relevant_lines_end,
                                         'original_suggestion': d})
            except Exception:
                get_logger().info(f"Could not parse suggestion: {d}")

        is_successful = self.git_provider.publish_code_suggestions(code_suggestions)
        if not is_successful:
            get_logger().info("Failed to publish code suggestions, trying to publish each suggestion separately")
            for code_suggestion in code_suggestions:
                self.git_provider.publish_code_suggestions([code_suggestion])
