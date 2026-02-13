from typing import Dict, List

from jinja2 import Environment, StrictUndefined

from pr_agent.algo.utils import load_yaml
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger
from pr_agent.tools.pr_code_suggestions_utils.helpers import validate_one_liner_suggestion_not_repeating_code


class ReflectionHandler:
    def __init__(self, core):
        self.core = core

    async def self_reflect_on_suggestions(self,
                                          suggestion_list: List,
                                          patches_diff: str,
                                          model: str,
                                          prev_suggestions_str: str = "",
                                          dedicated_prompt: str = "") -> str:
        if not suggestion_list:
            return ""

        try:
            suggestion_str = ""
            for i, suggestion in enumerate(suggestion_list):
                suggestion_str += f"suggestion {i + 1}: " + str(suggestion) + '\n\n'

            variables = {'suggestion_list': suggestion_list,
                         'suggestion_str': suggestion_str,
                         "diff": patches_diff,
                         'num_code_suggestions': len(suggestion_list),
                         'prev_suggestions_str': prev_suggestions_str,
                         "is_ai_metadata": get_settings().get("config.enable_ai_metadata", False),
                         'duplicate_prompt_examples': get_settings().config.get('duplicate_prompt_examples', False)}
            environment = Environment(undefined=StrictUndefined)  # nosec B701

            if dedicated_prompt:
                system_prompt_reflect = environment.from_string(
                    get_settings().get(dedicated_prompt).system).render(variables)
                user_prompt_reflect = environment.from_string(
                    get_settings().get(dedicated_prompt).user).render(variables)
            else:
                system_prompt_reflect = environment.from_string(
                    get_settings().pr_code_suggestions_reflect_prompt.system).render(variables)
                user_prompt_reflect = environment.from_string(
                    get_settings().pr_code_suggestions_reflect_prompt.user).render(variables)

            with get_logger().contextualize(command="self_reflect_on_suggestions"):
                response_reflect, finish_reason_reflect = await self.core.ai_handler.chat_completion(model=model,
                                                                                                system=system_prompt_reflect,
                                                                                                temperature=get_settings().config.temperature,
                                                                                                user=user_prompt_reflect)
        except Exception as e:
            get_logger().info(f"Could not reflect on suggestions, error: {e}")
            return ""
        return response_reflect

    async def analyze_self_reflection_response(self, data, response_reflect):
        response_reflect_yaml = load_yaml(response_reflect)
        code_suggestions_feedback = response_reflect_yaml.get("code_suggestions", [])
        if code_suggestions_feedback and len(code_suggestions_feedback) == len(data["code_suggestions"]):
            for i, suggestion in enumerate(data["code_suggestions"]):
                try:
                    suggestion["score"] = code_suggestions_feedback[i]["suggestion_score"]
                    suggestion["score_why"] = code_suggestions_feedback[i]["why"]

                    if 'relevant_lines_start' not in suggestion:
                        relevant_lines_start = code_suggestions_feedback[i].get('relevant_lines_start', -1)
                        relevant_lines_end = code_suggestions_feedback[i].get('relevant_lines_end', -1)
                        suggestion['relevant_lines_start'] = relevant_lines_start
                        suggestion['relevant_lines_end'] = relevant_lines_end
                        if relevant_lines_start < 0 or relevant_lines_end < 0:
                            suggestion["score"] = 0

                    try:
                        if get_settings().config.publish_output:
                            if not suggestion["score"]:
                                score = -1
                            else:
                                score = int(suggestion["score"])
                            label = suggestion["label"].lower().strip()
                            label = label.replace('<br>', ' ')
                            suggestion_statistics_dict = {'score': score,
                                                          'label': label}
                            get_logger().info(f"PR-Agent suggestions statistics",
                                              statistics=suggestion_statistics_dict, analytics=True)
                    except Exception as e:
                        get_logger().error(f"Failed to log suggestion statistics, error: {e}")
                        pass

                except Exception as e:  #
                    get_logger().error(f"Error processing suggestion score {i}",
                                       artifact={"suggestion": suggestion,
                                                 "code_suggestions_feedback": code_suggestions_feedback[i]})
                    suggestion["score"] = 7
                    suggestion["score_why"] = ""

                suggestion = validate_one_liner_suggestion_not_repeating_code(suggestion, self.core.git_provider)

                # if the before and after code is the same, clear one of them
                try:
                    if suggestion['existing_code'] == suggestion['improved_code']:
                        get_logger().debug(
                            f"edited improved suggestion {i + 1}, because equal to existing code: {suggestion['existing_code']}")
                        if get_settings().pr_code_suggestions.commitable_code_suggestions:
                            suggestion['improved_code'] = ""  # we need 'existing_code' to locate the code in the PR
                        else:
                            suggestion['existing_code'] = ""
                except Exception as e:
                    get_logger().error(f"Error processing suggestion {i + 1}, error: {e}")
