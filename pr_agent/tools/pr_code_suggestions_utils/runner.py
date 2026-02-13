import traceback
from pr_agent.log import get_logger
from pr_agent.config_loader import get_settings
from pr_agent.algo.pr_processing import retry_with_fallback_models
from pr_agent.algo.types import ModelType
from pr_agent.git_providers import GithubProvider
from pr_agent.servers.help import HelpMessage
from pr_agent.algo.utils import show_relevant_configurations
from pr_agent.tools.pr_code_suggestions_utils.helpers import (
    generate_summarized_suggestions,
    add_self_review_text,
    publish_persistent_comment_with_history
)

class SuggestionRunner:
    def __init__(self, tool):
        self.tool = tool

    async def run(self):
        try:
            if not self.tool.git_provider.get_files():
                get_logger().info(f"PR has no files: {self.tool.pr_url}, skipping code suggestions")
                return None

            get_logger().info('Generating code suggestions for PR...')

            # publish "Preparing suggestions..." comments
            if (get_settings().config.publish_output and get_settings().config.publish_output_progress and
                    not get_settings().config.get('is_auto_command', False)):
                if self.tool.git_provider.is_supported("gfm_markdown"):
                    self.tool.progress_response = self.tool.git_provider.publish_comment(self.tool.progress)
                else:
                    self.tool.git_provider.publish_comment("Preparing suggestions...", is_temporary=True)

            data = await retry_with_fallback_models(self.tool.prediction_handler.prepare_prediction_main, model_type=ModelType.REGULAR)
            if not data:
                data = {"code_suggestions": []}
            self.tool.data = data

            if (data is None or 'code_suggestions' not in data or not data['code_suggestions']):
                await self.tool.publish_no_suggestions()
                return

            if get_settings().config.publish_output:
                self.tool.git_provider.remove_initial_comment()
                if ((not get_settings().pr_code_suggestions.commitable_code_suggestions) and
                        self.tool.git_provider.is_supported("gfm_markdown")):

                    pr_body = generate_summarized_suggestions(data, self.tool.git_provider)
                    if get_settings().pr_code_suggestions.demand_code_suggestions_self_review:
                        pr_body = add_self_review_text(pr_body)

                    if (get_settings().pr_code_suggestions.enable_chat_text and get_settings().config.is_auto_command
                            and isinstance(self.tool.git_provider, GithubProvider)):
                        pr_body += "\n\n>💡 Need additional feedback ? start a [PR chat](https://chromewebstore.google.com/detail/ephlnjeghhogofkifjloamocljapahnl) \n\n"
                    if get_settings().pr_code_suggestions.enable_help_text:
                        pr_body += "<hr>\n\n<details> <summary><strong>💡 Tool usage guide:</strong></summary><hr> \n\n"
                        pr_body += HelpMessage.get_improve_usage_guide()
                        pr_body += "\n</details>\n"

                    if get_settings().get('config', {}).get('output_relevant_configurations', False):
                        pr_body += show_relevant_configurations(relevant_section='pr_code_suggestions')

                    if get_settings().pr_code_suggestions.persistent_comment:
                        publish_persistent_comment_with_history(self.tool.git_provider,
                                                                     pr_body,
                                                                     initial_header="## PR Code Suggestions ✨",
                                                                     update_header=True,
                                                                     name="suggestions",
                                                                     final_update_message=False,
                                                                     max_previous_comments=get_settings().pr_code_suggestions.max_history_len,
                                                                     progress_response=self.tool.progress_response)
                    else:
                        if self.tool.progress_response:
                            self.tool.git_provider.edit_comment(self.tool.progress_response, body=pr_body)
                        else:
                            self.tool.git_provider.publish_comment(pr_body)

                    if int(get_settings().pr_code_suggestions.dual_publishing_score_threshold) > 0:
                        await self.tool.dual_publishing(data)
                else:
                    await self.tool.push_inline_code_suggestions(data)
                    if self.tool.progress_response:
                        self.tool.git_provider.remove_comment(self.tool.progress_response)
            else:
                get_logger().info('Code suggestions generated for PR, but not published since publish_output is False.')
                pr_body = generate_summarized_suggestions(data, self.tool.git_provider)
                get_settings().data = {"artifact": pr_body}
                return
        except Exception as e:
            get_logger().error(f"Failed to generate code suggestions for PR, error: {e}",
                               artifact={"traceback": traceback.format_exc()})
            if get_settings().config.publish_output:
                if self.tool.progress_response:
                    self.tool.progress_response.delete()
                else:
                    try:
                        self.tool.git_provider.remove_initial_comment()
                        self.tool.git_provider.publish_comment(f"Failed to generate code suggestions for PR")
                    except Exception as e:
                        get_logger().exception(f"Failed to update persistent review, error: {e}")
