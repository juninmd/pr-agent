
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import json
from pr_agent.tools.pr_code_agent import PRCodeAgent
from pr_agent.config_loader import get_settings

class TestPRCodeAgent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Manually set settings for testing since they might not be loaded correctly in isolation
        get_settings().set("pr_code_agent.system_prompt", "System Prompt")
        get_settings().set("pr_code_agent.user_prompt", "Task: {{ task }}\nHistory: {{ history }}")
        get_settings().set("config.model", "gpt-4")
        get_settings().set("pr_code_agent.max_steps", 15)

    async def test_run_success(self):
        # Mock GitProvider
        mock_git_provider = MagicMock()
        mock_git_provider.get_pr_branch.return_value = "feature-branch"
        mock_git_provider.get_pr_file_content.return_value = "original content"

        # Mock AiHandler
        mock_ai_handler = MagicMock()
        mock_ai_handler_instance = AsyncMock()
        mock_ai_handler.return_value = mock_ai_handler_instance

        # Mock responses from AI
        # 1. read_file (NOT read_files)
        # 2. edit_file
        # 3. finish
        response_1 = '```json\n{"action": "read_file", "args": {"file_path": "file1.py"}}\n```'
        response_2 = '```json\n{"action": "edit_file", "args": {"file_path": "file1.py", "content": "new content"}}\n```'
        response_3 = '```json\n{"action": "finish", "args": {"message": "Done"}}\n```'

        mock_ai_handler_instance.chat_completion.side_effect = [
            [response_1], [response_2], [response_3]
        ]

        # Initialize Agent
        with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_git_provider):
            agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["fix bug"], ai_handler=mock_ai_handler)
            await agent.run()

        # Verify interactions
        # 1. Check if AI was called 3 times
        self.assertEqual(mock_ai_handler_instance.chat_completion.call_count, 3)

        # 2. Check if git provider methods were called
        mock_git_provider.get_pr_file_content.assert_called_with("file1.py", "feature-branch")
        mock_git_provider.create_or_update_pr_file.assert_called_with(
            "file1.py", "feature-branch", "new content", "Agent edit"
        )
        mock_git_provider.publish_comment.assert_called_with("Task Done: Done")

    async def test_run_invalid_json(self):
        # Mock GitProvider
        mock_git_provider = MagicMock()

        # Mock AiHandler
        mock_ai_handler = MagicMock()
        mock_ai_handler_instance = AsyncMock()
        mock_ai_handler.return_value = mock_ai_handler_instance

        # Invalid JSON response
        mock_ai_handler_instance.chat_completion.return_value = ["invalid json"]

        with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=mock_git_provider):
            agent = PRCodeAgent("https://github.com/org/repo/pull/1", args=["fix bug"], ai_handler=mock_ai_handler)
            await agent.run()

        # Should continue for max_steps attempts (default 15)
        self.assertEqual(mock_ai_handler_instance.chat_completion.call_count, 15)
