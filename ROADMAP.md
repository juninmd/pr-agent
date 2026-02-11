# Product Roadmap: PR-Agent

## 1. Vision & Goals

**Vision:** To be the premier open-source AI-powered code review agent and autonomous developer companion, fostering developer productivity and code quality through intelligent automation, customization, and platform-agnostic support.

**Goals:**
*   Provide high-quality, actionable feedback on Pull Requests across all major Git providers (GitHub, GitLab, Bitbucket, Azure DevOps, Gitea).
*   **Empower developers with an autonomous coding agent (`/code`) that generates clean, maintainable code.**
*   Maintain a thriving open-source community that drives feature development and governance.
*   Ensure seamless integration with existing developer workflows (CI/CD, CLI, etc.).
*   Offer flexibility through extensive configuration options and support for multiple LLM providers (OpenAI, Gemini, etc.).

## 2. Current Status

The project is currently a mature, feature-rich tool offering automated PR description generation (`/describe`), code review (`/review`), suggestions (`/improve`), and interactive chat (`/ask`).

**Key Highlights:**
*   **Autonomous Capabilities:** The `/code` tool (Autonomous Agent) enables autonomous code changes with self-correction and strict compliance checks (Clean Code, DRY, SRP, KISS).
*   **Transition Phase:** Moving towards a community-governed model (donated to an open-source foundation).
*   **Stable Features:** Core review and description functionalities are widely used and stable.
*   **Token Economy:** Initial implementation of token-saving strategies for cost-effective usage.

## 3. Quarterly Roadmap (2025)

### Q1 2025: Foundation & Stability
**Focus:** Establishing governance, improving documentation, and addressing technical debt.

*   **High Priority:**
    *   **Governance:** Finalize Open Source Foundation transition and community contribution guidelines.
    *   **Technical Debt:** Address TODO in `pr_agent/servers/github_app.py` regarding commit filtering logic (filter bot/merge commits in push triggers).
*   **Medium Priority:**
    *   **Documentation:** Enhance documentation for self-hosting and advanced configuration.
    *   **Onboarding:** Improve onboarding experience for new contributors.
*   **Low Priority:**
    *   **Cleanup:** Address technical debt in `pr_agent/custom_merge_loader.py` regarding Dynaconf `settings_files` attribute check.
    *   **Refactoring:** Ensure core Agent components adhere to strict coding standards (Clean Code, max 150 lines/file).

### Q2 2025: Local Development Experience
**Focus:** Enhancing the local development workflow and CLI capabilities.

*   **High Priority:**
    *   **Enhancement:** Address TODO in `pr_agent/git_providers/local_git_provider.py` to improve PR description generation using LLM summarization.
*   **Medium Priority:**
    *   **CLI:** Improve CLI argument handling and help messages for local agent runs.
    *   **Testing:** Expand local testing scenarios for better coverage.
*   **Low Priority:**
    *   **UX:** Refine local output formatting for better readability.

### Q3 2025: Enterprise Integrations
**Focus:** Expanding platform support and refining enterprise-grade features.

*   **High Priority:**
    *   **Feature:** Address TODO in `pr_agent/git_providers/codecommit_provider.py` to support multiple target branches in AWS CodeCommit PRs.
*   **Medium Priority:**
    *   **Parity:** Improve Bitbucket and Azure DevOps integration parity with GitHub/GitLab.
    *   **Security:** Enhance security auditing and dependency management.
*   **Low Priority:**
    *   **Performance:** Optimize CI/CD pipelines for faster PR checks.

### Q4 2025: Optimization & Performance
**Focus:** Optimizing for large repositories and reducing operational costs.

*   **High Priority:**
    *   **Optimization:** Address TODO in `pr_agent/algo/diff_processing.py` to implement smart hunk removal logic to reduce token usage in large PRs.
*   **Medium Priority:**
    *   **Scaling:** Performance tuning for high-concurrency environments.
    *   **Caching:** Advanced caching strategies for repetitive analysis.
*   **Low Priority:**
    *   **Economy:** Refine "Token Economy" mode based on usage data.

## 4. Feature Details

### Support for Multiple Targets in CodeCommit
*   **User Value Proposition:** Enables users on AWS CodeCommit to analyze PRs that span multiple target branches or have complex merge strategies, ensuring comprehensive review coverage.
*   **Technical Approach:** Update `CodeCommitProvider` to handle list-based target inputs and iterate over diffs for each target, aggregating the results.
*   **Success Criteria:** Valid PR analysis generated for CodeCommit PRs with >1 target branch.
*   **Estimated Effort:** Medium

### Smart Hunk Removal (Token Optimization)
*   **User Value Proposition:** Reduces API costs and latency for large PRs by intelligently excluding less relevant code changes (e.g., auto-generated files, large asset moves) from the analysis context.
*   **Technical Approach:** Implement a heuristic-based filter in `pr_agent/algo/diff_processing.py` that scores diff hunks based on relevance and drops the lowest-scoring ones when the token limit is approached.
*   **Success Criteria:** 20% reduction in average token usage for PRs > 1000 lines without degradation in review quality.
*   **Estimated Effort:** Large

### Enhanced Local PR Description
*   **User Value Proposition:** Provides more meaningful context for local development changes, making it easier to review and merge local work.
*   **Technical Approach:** Leverage LLM summarization (e.g., GPT-3.5/4o-mini) in `LocalGitProvider.get_pr_description_full` to generate a concise summary of local commits instead of just concatenating messages.
*   **Success Criteria:** High-quality, coherent PR descriptions generated for local changes.
*   **Estimated Effort:** Small

### Autonomous Agent Compliance (`/code`)
*   **User Value Proposition:** Ensures that code generated by the agent is maintainable, readable, and easy to review by enforcing strict Clean Code standards and file size limits.
*   **Technical Approach:** Continuous improvement of the `edit_file` tool's self-correction mechanism and integration of linter checks in the agent's feedback loop.
*   **Success Criteria:** Zero "oversized file" errors in generated code; high user acceptance of agent-generated PRs.
*   **Estimated Effort:** Medium

## 5. Dependencies & Risks

*   **LLM API Costs:** Fluctuations in pricing or rate limits from providers (OpenAI, Google, Anthropic) could impact usage costs and availability.
*   **Model Availability:** Dependence on specific model versions requires adaptability to model deprecations or behavior changes.
*   **Community Engagement:** The success of the transition to community governance relies on active and sustained contribution from maintainers.
*   **Platform API Changes:** Breaking changes in GitHub/GitLab/Bitbucket APIs could temporarily disrupt service.
*   **Complex Refactoring:** Enforcing strict architectural limits on core components may require significant refactoring effort and careful regression testing.
