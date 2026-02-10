# Product Roadmap: PR-Agent

## 1. Vision & Goals

**Vision:** To be the premier open-source AI-powered code review agent, fostering developer productivity and code quality through intelligent automation, customization, and platform-agnostic support.

**Goals:**
*   Provide high-quality, actionable feedback on Pull Requests across all major Git providers.
*   Maintain a thriving open-source community that drives feature development and governance.
*   Ensure seamless integration with existing developer workflows (GitHub Actions, GitLab CI/CD, etc.).
*   Offer flexibility through extensive configuration options and support for multiple LLM providers.

## 2. Current Status

The project is currently a mature, feature-rich tool offering automated PR description generation (`/describe`), code review (`/review`), suggestions (`/improve`), and interactive chat (`/ask`). It supports GitHub, GitLab, Bitbucket, Azure DevOps, and Gitea.

**Key Highlights:**
*   **Transition Phase:** Moving towards a community-governed model (donated to an open-source foundation).
*   **Stable Features:** Core review and description functionalities are widely used and stable.
*   **Token Economy:** Initial implementation of token-saving strategies for cost-effective usage.

## 3. Quarterly Roadmap

### Q1 2024: Community Transition & Stability
**Focus:** Establishing governance, improving documentation, and addressing technical debt.

*   **High Priority:**
    *   Formalize governance model and community contribution guidelines.
    *   Setup automated release processes for community maintainers.
*   **Medium Priority:**
    *   Enhance documentation for self-hosting and advanced configuration.
    *   Improve onboarding experience for new contributors.
*   **Low Priority (Technical Debt):**
    *   Address TODOs in `pr_agent/servers/github_app.py` regarding commit filtering logic.
    *   Refactor `pr_agent/git_providers/local_git_provider.py` to improve description handling.

### Q2 2024: Enhanced Integrations
**Focus:** Expanding platform support and refining existing integrations.

*   **High Priority:**
    *   **Feature:** Support for multiple target branches in AWS CodeCommit PRs (from TODO in `codecommit_provider.py`).
*   **Medium Priority:**
    *   Improve Bitbucket and Azure DevOps integration parity with GitHub/GitLab.
    *   Enhance `LocalGitProvider` for better local testing and development workflows.
*   **Low Priority:**
    *   Optimize CI/CD pipelines for faster PR checks.

### Q3 2024: Advanced AI Capabilities
**Focus:** Leveraging next-generation models and improving context awareness.

*   **High Priority:**
    *   **Feature:** Full integration and optimization for GPT-5 and Gemini 1.5 Pro models.
    *   **Feature:** Enhanced RAG (Retrieval-Augmented Generation) for deeper codebase understanding.
*   **Medium Priority:**
    *   Semantic code search improvements for better context retrieval.
    *   Customizable persona definitions for different team styles.
*   **Low Priority:**
    *   Experiment with local LLM support for privacy-focused deployments.

### Q4 2024: Performance & Scale
**Focus:** Optimizing for large repositories and enterprise-grade workloads.

*   **High Priority:**
    *   **Optimization:** Implement smarter hunk removal logic to reduce token usage in large PRs (from TODO in `diff_processing.py`).
*   **Medium Priority:**
    *   Performance tuning for high-concurrency environments.
    *   Advanced caching strategies for repetitive analysis.
*   **Low Priority:**
    *   Refine "Token Economy" mode based on usage data.

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

## 5. Dependencies & Risks

*   **LLM API Costs:** Fluctuations in pricing or rate limits from providers (OpenAI, Google, Anthropic) could impact usage costs and availability.
*   **Model Availability:** Dependence on specific model versions (e.g., GPT-4) requires adaptability to model deprecations or behavior changes.
*   **Community Engagement:** The success of the transition to community governance relies on active and sustained contribution from maintainers.
*   **Platform API Changes:** Breaking changes in GitHub/GitLab/Bitbucket APIs could temporarily disrupt service.
