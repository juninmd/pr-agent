import pytest
import os
import shutil
import tempfile
from unittest.mock import MagicMock
from pr_agent.tools.code_agent.tools import AgentTools

class TestAgentToolsLocalSync:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        yield
        # Teardown
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    @pytest.mark.asyncio
    async def test_edit_file_syncs_locally(self):
        # Mock GitProvider
        mock_provider = MagicMock()
        mock_provider.get_pr_branch.return_value = "feature-branch"

        tools = AgentTools(mock_provider)

        file_path = "test_file.txt"
        content = "Hello, World!"

        # 1. Edit the file (should create it locally too)
        # Note: We simulate that we are in a repo by creating .git directory
        os.mkdir(".git")

        await tools.edit_file(file_path, content)

        # 2. Verify Provider call
        mock_provider.create_or_update_pr_file.assert_called_once()

        # 3. Verify Local File existence and content
        assert os.path.exists(file_path)
        with open(file_path, "r") as f:
            read_content = f.read()
        assert read_content == content

        # 4. Verify run_in_bash_session sees it
        res = await tools.run_in_bash_session(f"cat {file_path}")
        assert "Hello, World!" in res

    @pytest.mark.asyncio
    async def test_delete_file_syncs_locally(self):
        # Mock GitProvider
        mock_provider = MagicMock()

        tools = AgentTools(mock_provider)
        file_path = "to_delete.txt"

        # Setup
        with open(file_path, "w") as f:
            f.write("delete me")

        assert os.path.exists(file_path)

        # Action
        await tools.delete_file(file_path)

        # Verify
        assert not os.path.exists(file_path)
