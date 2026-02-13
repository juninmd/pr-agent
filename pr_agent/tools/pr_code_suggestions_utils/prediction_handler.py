import asyncio
import copy
from typing import Dict, List

from jinja2 import Environment, StrictUndefined

from pr_agent.algo import MAX_TOKENS
from pr_agent.algo.git_patch_processing import decouple_and_convert_to_hunks_with_lines_numbers
from pr_agent.algo.pr_processing import get_pr_diff, get_pr_multi_diffs
from pr_agent.algo.utils import clip_tokens, get_max_tokens, get_model, load_yaml
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger
from pr_agent.tools.pr_code_suggestions_utils.helpers import remove_line_numbers


class PredictionHandler:
    def __init__(self, core):
        self.core = core

    async def prepare_prediction(self, model: str) -> dict:
        self.core.patches_diff = get_pr_diff(self.core.git_provider,
                                        self.core.token_handler,
                                        model,
                                        add_line_numbers_to_hunks=True,
                                        disable_extra_lines=False)
        self.core.patches_diff_list = [self.core.patches_diff]
        self.core.patches_diff_no_line_number = remove_line_numbers([self.core.patches_diff])[0]

        if self.core.patches_diff:
            get_logger().debug(f"PR diff", artifact=self.core.patches_diff)
            self.core.prediction = await self.get_prediction(model, self.core.patches_diff, self.core.patches_diff_no_line_number)
        else:
            get_logger().warning(f"Empty PR diff")
            self.core.prediction = None

        data = self.core.prediction
        return data

    async def get_prediction(self, model: str, patches_diff: str, patches_diff_no_line_number: str) -> dict:
        variables = copy.deepcopy(self.core.vars)
        variables["diff"] = patches_diff  # update diff
        variables["diff_no_line_numbers"] = patches_diff_no_line_number  # update diff
        environment = Environment(undefined=StrictUndefined)  # nosec B701
        system_prompt = environment.from_string(self.core.pr_code_suggestions_prompt_system).render(variables)
        user_prompt = environment.from_string(get_settings().pr_code_suggestions_prompt.user).render(variables)
        response, finish_reason = await self.core.ai_handler.chat_completion(
            model=model, temperature=get_settings().config.temperature, system=system_prompt, user=user_prompt)
        if not get_settings().config.publish_output:
            get_settings().system_prompt = system_prompt
            get_settings().user_prompt = user_prompt

        # load suggestions from the AI response
        data = self.core._prepare_pr_code_suggestions(response)

        # self-reflect on suggestions (mandatory, since line numbers are generated now here)
        model_reflect_with_reasoning = get_model('model_reasoning')
        fallbacks = get_settings().config.fallback_models
        if model_reflect_with_reasoning == get_settings().config.model and model != get_settings().config.model and fallbacks and model == \
                fallbacks[0]:
            # we are using a fallback model (should not happen on regular conditions)
            get_logger().warning(f"Using the same model for self-reflection as the one used for suggestions")
            model_reflect_with_reasoning = model

        # We access self_reflect_on_suggestions from the core, which will use ReflectionHandler
        response_reflect = await self.core.reflection_handler.self_reflect_on_suggestions(data["code_suggestions"],
                                                                  patches_diff, model=model_reflect_with_reasoning)
        if response_reflect:
            await self.core.reflection_handler.analyze_self_reflection_response(data, response_reflect)
        else:
            # get_logger().error(f"Could not self-reflect on suggestions. using default score 7")
            for i, suggestion in enumerate(data["code_suggestions"]):
                suggestion["score"] = 7
                suggestion["score_why"] = ""

        return data

    async def prepare_prediction_main(self, model: str) -> dict:
        # get PR diff
        if get_settings().pr_code_suggestions.decouple_hunks:
            self.core.patches_diff_list = get_pr_multi_diffs(self.core.git_provider,
                                                        self.core.token_handler,
                                                        model,
                                                        max_calls=get_settings().pr_code_suggestions.max_number_of_calls,
                                                        add_line_numbers=True)  # decouple hunk with line numbers
            self.core.patches_diff_list_no_line_numbers = remove_line_numbers(self.core.patches_diff_list)  # decouple hunk

        else:
            # non-decoupled hunks
            self.core.patches_diff_list_no_line_numbers = get_pr_multi_diffs(self.core.git_provider,
                                                                        self.core.token_handler,
                                                                        model,
                                                                        max_calls=get_settings().pr_code_suggestions.max_number_of_calls,
                                                                        add_line_numbers=False)
            self.core.patches_diff_list = await self.convert_to_decoupled_with_line_numbers(
                self.core.patches_diff_list_no_line_numbers, model)
            if not self.core.patches_diff_list:
                # fallback to decoupled hunks
                self.core.patches_diff_list = get_pr_multi_diffs(self.core.git_provider,
                                                            self.core.token_handler,
                                                            model,
                                                            max_calls=get_settings().pr_code_suggestions.max_number_of_calls,
                                                            add_line_numbers=True)  # decouple hunk with line numbers

        if self.core.patches_diff_list:
            get_logger().info(f"Number of PR chunk calls: {len(self.core.patches_diff_list)}")
            get_logger().debug(f"PR diff:", artifact=self.core.patches_diff_list)

            # parallelize calls to AI:
            if get_settings().pr_code_suggestions.parallel_calls:
                prediction_list = await asyncio.gather(
                    *[self.get_prediction(model, patches_diff, patches_diff_no_line_numbers) for
                      patches_diff, patches_diff_no_line_numbers in
                      zip(self.core.patches_diff_list, self.core.patches_diff_list_no_line_numbers)])
                self.core.prediction_list = prediction_list
            else:
                prediction_list = []
                for patches_diff, patches_diff_no_line_numbers in zip(self.core.patches_diff_list, self.core.patches_diff_list_no_line_numbers):
                    prediction = await self.get_prediction(model, patches_diff, patches_diff_no_line_numbers)
                    prediction_list.append(prediction)

            data = {"code_suggestions": []}
            for j, predictions in enumerate(prediction_list):  # each call adds an element to the list
                if "code_suggestions" in predictions:
                    score_threshold = max(1, int(get_settings().pr_code_suggestions.suggestions_score_threshold))
                    for i, prediction in enumerate(predictions["code_suggestions"]):
                        try:
                            score = int(prediction.get("score", 1))
                            if score >= score_threshold:
                                data["code_suggestions"].append(prediction)
                            else:
                                get_logger().info(
                                    f"Removing suggestions {i} from call {j}, because score is {score}, and score_threshold is {score_threshold}",
                                    artifact=prediction)
                        except Exception as e:
                            get_logger().error(f"Error getting PR diff for suggestion {i} in call {j}, error: {e}",
                                               artifact={"prediction": prediction})
            self.core.data = data
        else:
            get_logger().warning(f"Empty PR diff list")
            self.core.data = data = None
        return data

    async def convert_to_decoupled_with_line_numbers(self, patches_diff_list_no_line_numbers, model) -> List[str]:
        with get_logger().contextualize(sub_feature='convert_to_decoupled_with_line_numbers'):
            try:
                patches_diff_list = []
                for patch_prompt in patches_diff_list_no_line_numbers:
                    file_prefix = "## File: "
                    patches = patch_prompt.strip().split(f"\n{file_prefix}")
                    patches_new = copy.deepcopy(patches)
                    for i in range(len(patches_new)):
                        if i == 0:
                            prefix = patches_new[i].split("\n@@")[0].strip()
                        else:
                            prefix = file_prefix + patches_new[i].split("\n@@")[0][1:]
                            prefix = prefix.strip()
                        patches_new[i] = prefix + '\n\n' + decouple_and_convert_to_hunks_with_lines_numbers(patches_new[i],
                                                                                                          file=None).strip()
                        patches_new[i] = patches_new[i].strip()
                    patch_final = "\n\n\n".join(patches_new)
                    if model in MAX_TOKENS:
                        max_tokens_full = MAX_TOKENS[
                            model]  # note - here we take the actual max tokens, without any reductions. we do aim to get the full documentation website in the prompt
                    else:
                        max_tokens_full = get_max_tokens(model)
                    delta_output = 2000
                    token_count = self.core.token_handler.count_tokens(patch_final)
                    if token_count > max_tokens_full - delta_output:
                        get_logger().warning(
                            f"Token count {token_count} exceeds the limit {max_tokens_full - delta_output}. clipping the tokens")
                        patch_final = clip_tokens(patch_final, max_tokens_full - delta_output)
                    patches_diff_list.append(patch_final)
                return patches_diff_list
            except Exception as e:
                get_logger().exception(f"Error converting to decoupled with line numbers",
                                       artifact={'patches_diff_list_no_line_numbers': patches_diff_list_no_line_numbers})
                return []
