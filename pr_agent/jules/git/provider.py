from abc import ABC, abstractmethod
from typing import List, Optional

class GitProvider(ABC):
    """
    Abstract Base Class for Git Providers.
    Defines the contract for interacting with GitHub, GitLab, etc.
    Strictly optimized for Clean Code and < 150 LOC.
    """

    @abstractmethod
    def get_pr_url(self) -> str:
        """Returns the URL of the current PR."""
        pass

    @abstractmethod
    def get_files(self) -> List[str]:
        """Returns a list of files modified in the PR."""
        pass

    @abstractmethod
    def get_file_content(self, file_path: str, branch: Optional[str] = None) -> str:
        """Returns the content of a file."""
        pass

    @abstractmethod
    def create_or_update_file(self, file_path: str, content: str, message: str, branch: str) -> None:
        """Creates or updates a file in the repository."""
        pass

    @abstractmethod
    def create_pr(self, title: str, body: str, source_branch: str, target_branch: str) -> str:
        """Creates a new Pull Request."""
        pass

    @abstractmethod
    def add_comment(self, body: str) -> None:
        """Adds a comment to the PR."""
        pass
