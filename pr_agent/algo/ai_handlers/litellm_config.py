import os
import litellm
import openai
from pr_agent.config_loader import get_settings
from pr_agent.algo.ai_handlers.litellm_helpers import _get_azure_ad_token

class LiteLLMConfig:
    def __init__(self):
        self.azure = False
        self.api_base = None
        self.repetition_penalty = None

        self._configure_litellm()
        self._configure_openai()
        self._configure_aws()
        self._configure_azure()
        self._configure_other_providers()

    def _configure_litellm(self):
        if get_settings().get("LITELLM.DISABLE_AIOHTTP", False):
            litellm.disable_aiohttp_transport = True

        if get_settings().get("LITELLM.DROP_PARAMS", None):
            litellm.drop_params = get_settings().litellm.drop_params
        if get_settings().get("LITELLM.SUCCESS_CALLBACK", None):
            litellm.success_callback = get_settings().litellm.success_callback
        if get_settings().get("LITELLM.FAILURE_CALLBACK", None):
            litellm.failure_callback = get_settings().litellm.failure_callback
        if get_settings().get("LITELLM.SERVICE_CALLBACK", None):
            litellm.service_callback = get_settings().litellm.service_callback

    def _configure_openai(self):
        if get_settings().get("OPENAI.KEY", None):
            openai.api_key = get_settings().openai.key
            litellm.openai_key = get_settings().openai.key
        elif 'OPENAI_API_KEY' not in os.environ:
            litellm.api_key = "dummy_key"

        if get_settings().get("OPENAI.ORG", None):
            litellm.organization = get_settings().openai.org
        if get_settings().get("OPENAI.API_TYPE", None):
            if get_settings().openai.api_type == "azure":
                self.azure = True
                litellm.azure_key = get_settings().openai.key
        if get_settings().get("OPENAI.API_VERSION", None):
            litellm.api_version = get_settings().openai.api_version
        if get_settings().get("OPENAI.API_BASE", None):
            litellm.api_base = get_settings().openai.api_base
            self.api_base = get_settings().openai.api_base

    def _configure_aws(self):
        if get_settings().get("aws.AWS_ACCESS_KEY_ID"):
            assert get_settings().aws.AWS_SECRET_ACCESS_KEY and get_settings().aws.AWS_REGION_NAME, "AWS credentials are incomplete"
            os.environ["AWS_ACCESS_KEY_ID"] = get_settings().aws.AWS_ACCESS_KEY_ID
            os.environ["AWS_SECRET_ACCESS_KEY"] = get_settings().aws.AWS_SECRET_ACCESS_KEY
            os.environ["AWS_REGION_NAME"] = get_settings().aws.AWS_REGION_NAME

    def _configure_azure(self):
        # Check for Azure AD configuration
        if get_settings().get("AZURE_AD.CLIENT_ID", None):
            self.azure = True
            # Generate access token using Azure AD credentials from settings
            access_token = _get_azure_ad_token()
            litellm.api_key = access_token
            openai.api_key = access_token

            # Set API base from settings
            self.api_base = get_settings().azure_ad.api_base
            litellm.api_base = self.api_base
            openai.api_base = self.api_base

    def _configure_other_providers(self):
        if get_settings().get("ANTHROPIC.KEY", None):
            litellm.anthropic_key = get_settings().anthropic.key
        if get_settings().get("COHERE.KEY", None):
            litellm.cohere_key = get_settings().cohere.key
        if get_settings().get("GROQ.KEY", None):
            litellm.api_key = get_settings().groq.key
        if get_settings().get("REPLICATE.KEY", None):
            litellm.replicate_key = get_settings().replicate.key
        if get_settings().get("XAI.KEY", None):
            litellm.api_key = get_settings().xai.key
        if get_settings().get("HUGGINGFACE.KEY", None):
            litellm.huggingface_key = get_settings().huggingface.key
        if get_settings().get("HUGGINGFACE.API_BASE", None) and 'huggingface' in get_settings().config.model:
            litellm.api_base = get_settings().huggingface.api_base
            self.api_base = get_settings().huggingface.api_base
        if get_settings().get("OLLAMA.API_BASE", None):
            litellm.api_base = get_settings().ollama.api_base
            self.api_base = get_settings().ollama.api_base
        if get_settings().get("HUGGINGFACE.REPETITION_PENALTY", None):
            self.repetition_penalty = float(get_settings().huggingface.repetition_penalty)
        if get_settings().get("VERTEXAI.VERTEX_PROJECT", None):
            litellm.vertex_project = get_settings().vertexai.vertex_project
            litellm.vertex_location = get_settings().get(
                "VERTEXAI.VERTEX_LOCATION", None
            )
        # Google AI Studio
        if get_settings().get("GOOGLE_AI_STUDIO.GEMINI_API_KEY", None):
          os.environ["GEMINI_API_KEY"] = get_settings().google_ai_studio.gemini_api_key

        # Support deepseek models
        if get_settings().get("DEEPSEEK.KEY", None):
            os.environ['DEEPSEEK_API_KEY'] = get_settings().get("DEEPSEEK.KEY")

        # Support deepinfra models
        if get_settings().get("DEEPINFRA.KEY", None):
            os.environ['DEEPINFRA_API_KEY'] = get_settings().get("DEEPINFRA.KEY")

        # Support mistral models
        if get_settings().get("MISTRAL.KEY", None):
            os.environ["MISTRAL_API_KEY"] = get_settings().get("MISTRAL.KEY")

        # Support codestral models
        if get_settings().get("CODESTRAL.KEY", None):
            os.environ["CODESTRAL_API_KEY"] = get_settings().get("CODESTRAL.KEY")

        # Support for Openrouter models
        if get_settings().get("OPENROUTER.KEY", None):
            openrouter_api_key = get_settings().get("OPENROUTER.KEY", None)
            os.environ["OPENROUTER_API_KEY"] = openrouter_api_key
            litellm.api_key = openrouter_api_key
            openai.api_key = openrouter_api_key

            openrouter_api_base = get_settings().get("OPENROUTER.API_BASE", "https://openrouter.ai/api/v1")
            os.environ["OPENROUTER_API_BASE"] = openrouter_api_base
            self.api_base = openrouter_api_base
            litellm.api_base = openrouter_api_base
