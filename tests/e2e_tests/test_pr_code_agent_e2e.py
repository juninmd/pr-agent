import unittest
import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from git import Repo

from pr_agent.tools.pr_code_agent import PRCodeAgent
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.local_git_provider import LocalGitProvider

class TestPRCodeAgentE2E(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.repo = Repo.init(self.test_dir)

        # Initialize with a commit so we have a branch
        file_path = os.path.join(self.test_dir, "init.txt")
        with open(file_path, "w") as f:
            f.write("init")
        self.repo.index.add([file_path])
        self.repo.index.commit("Initial commit")

        # Patch _find_repository_root to return our temp dir
        self.patcher = patch('pr_agent.git_providers.local_git_provider._find_repository_root', return_value=Path(self.test_dir))
        self.patcher.start()

        # Update settings
        get_settings().set("config.git_provider", "local")
        get_settings().set("pr_code_agent.system_prompt", "System Prompt")
        get_settings().set("pr_code_agent.user_prompt", "Task: {{task}}\nRelevant files: {{relevant_files}}\nHistory: {{history}}")


    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)

    async def test_e2e_create_files(self):
        # Define the task
        task = "Create a hello.js file with 'console.log(\"Hello World\");' and a README.md with '# Documentation'"

        # Mock AI Handler (simulating Ollama/LLM)
        mock_ai_handler = MagicMock()
        mock_instance = MagicMock()
        mock_ai_handler.return_value = mock_instance

        # Define the sequence of responses the agent would receive from the LLM
        # 1. Edit hello.js
        response_1 = '```json\n{"action": "edit_file", "args": {"file_path": "hello.js", "content": "console.log(\\"Hello World\\");"}}\n```'
        # 2. Edit README.md
        response_2 = '```json\n{"action": "edit_file", "args": {"file_path": "README.md", "content": "# Documentation"}}\n```'
        # 3. Finish
        response_3 = '```json\n{"action": "finish", "args": {"message": "Files created."}}\n```'

        # Setup the async method
        async def mock_chat_completion(*args, **kwargs):
             # Simple state machine simulation
            if mock_chat_completion.counter == 0:
                mock_chat_completion.counter += 1
                return response_1, "stop"
            elif mock_chat_completion.counter == 1:
                mock_chat_completion.counter += 1
                return response_2, "stop"
            else:
                return response_3, "stop"

        mock_chat_completion.counter = 0
        mock_instance.chat_completion = mock_chat_completion

        # Run the agent
        # We need to ensure get_git_provider returns our LocalGitProvider instance initialized with our temp dir
        # But LocalGitProvider inits using _find_repository_root which we patched.

        # We also need to patch get_git_provider_with_context to return a LocalGitProvider
        # correctly initialized.

        local_provider = LocalGitProvider(target_branch_name="master") # master or main depending on git version
        # Git init might create 'master' or 'main'. Let's check.
        try:
            local_provider = LocalGitProvider(target_branch_name=self.repo.active_branch.name)
        except:
             local_provider = LocalGitProvider(target_branch_name="master")


        with patch('pr_agent.tools.pr_code_agent.get_git_provider_with_context', return_value=local_provider):
            agent = PRCodeAgent("local_url_placeholder", args=[task], ai_handler=mock_ai_handler)
            await agent.run()

        # Validate results
        hello_js_path = os.path.join(self.test_dir, "hello.js")
        readme_path = os.path.join(self.test_dir, "README.md")

        self.assertTrue(os.path.exists(hello_js_path), "hello.js should exist")
        with open(hello_js_path, "r") as f:
            content = f.read()
            self.assertIn("console.log(\"Hello World\");", content)

        self.assertTrue(os.path.exists(readme_path), "README.md should exist")
        with open(readme_path, "r") as f:
            content = f.read()
            self.assertIn("# Documentation", content)

        print("Test E2E Passed: Files created successfully.")
