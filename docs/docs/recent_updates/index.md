# Recent Updates and Future Roadmap

`Page last updated: 2025-07-20`

This page summarizes recent enhancements to Qodo Merge (last three months).

It also outlines our development roadmap for the upcoming three months. Please note that the roadmap is subject to change, and features may be adjusted, added, or reprioritized.

=== "Recent Updates"
    - [2025-07-20] **PR to Ticket**: Generate tickets in your tracking systems based on PR content. ([Learn more](https://qodo-merge-docs.qodo.ai/tools/pr_to_ticket/))
    - [2025-07-17] **Compliance**: Comprehensive compliance checks for security, ticket requirements, and custom organizational rules. ([Learn more](https://qodo-merge-docs.qodo.ai/tools/compliance/))
    - **Gitlab Issues Support**: Qodo Merge now supports Gitlab issues for ticket context retrieval and ticket creation.
    - **Receiving Qodo Merge feedback locally**: You can receive automatic feedback from Qodo Merge on your local IDE after each commit. ([Learn more](https://github.com/qodo-ai/agents/tree/main/agents/qodo-merge-post-commit))
    - **Mermaid Diagrams**: Qodo Merge now generates by default Mermaid diagrams for PRs, providing a visual representation of code changes. ([Learn more](https://qodo-merge-docs.qodo.ai/tools/describe/#sequence-diagram-support))
    - **Best Practices Hierarchy**: Introducing support for structured best practices, such as for folders in monorepos or a unified best practice file for a group of repositories. ([Learn more](https://qodo-merge-docs.qodo.ai/tools/improve/#global-hierarchical-best-practices))
    - **Simplified Free Tier**: Qodo Merge now offers a simplified free tier with a monthly limit of 75 PR reviews per organization, replacing the previous two-week trial. ([Learn more](https://qodo-merge-docs.qodo.ai/installation/qodo_merge/#cloud-users))
    - **CLI Endpoint**: A new Qodo Merge endpoint that accepts a lists of before/after code changes, executes Qodo Merge commands, and return the results. Currently available for enterprise customers. Contact [Qodo](https://www.qodo.ai/contact/) for more information.
    - **Linear tickets support**: Qodo Merge now supports Linear tickets. ([Learn more](https://qodo-merge-docs.qodo.ai/core-abilities/fetching_ticket_context/#linear-integration))
    - **Smart Update**: Upon PR updates, Qodo Merge will offer tailored code suggestions, addressing both the entire PR and the specific incremental changes since the last feedback. ([Learn more](https://qodo-merge-docs.qodo.ai/core-abilities/incremental_update/))

=== "Future Roadmap"
    - **`Compliance` tool to replace `review` as default**: Planning to make the `compliance` tool the default automatic command instead of the current `review` tool.
    - **Smarter context retrieval**: Leverage AST and LSP analysis to gather relevant context from across the entire repository.
    - **Enhanced portal experience**: Improved user experience in the Qodo Merge portal with new options and capabilities.
