`Platforms supported: GitHub, GitLab, Bitbucket`

## Overview

The `compliance` tool performs comprehensive compliance checks on PR code changes, validating them against security standards, ticket requirements, and custom organizational compliance checklists, thereby helping teams maintain consistent code quality and security practices while ensuring that development work aligns with business requirements.

=== "Fully Compliant"
    ![compliance_overview](https://codium.ai/images/pr_agent/compliance_full.png){width=256}

=== "Partially Compliant"
    ![compliance_overview](https://codium.ai/images/pr_agent/compliance_partial.png){width=256}

___

[//]: # (???+ note "The following features are available only for Qodo Merge 💎 users:")

[//]: # (    - Custom compliance checklists and hierarchical compliance checklists)

[//]: # (    - Ticket compliance validation with Jira/Linear integration)

[//]: # (    - Auto-approval based on compliance status)

[//]: # (    - Compliance labels and automated enforcement)

## Example Usage

### Manual Triggering

Invoke the tool manually by commenting `/compliance` on any PR. The compliance results are presented in a comprehensive table:

To edit [configurations](#configuration-options) related to the `compliance` tool, use the following template:

```toml
/compliance --pr_compliance.some_config1=... --pr_compliance.some_config2=...
```

For example, you can enable ticket compliance labels by running:

```toml
/compliance --pr_compliance.enable_ticket_labels=true
```

### Automatic Triggering


The tool can be triggered automatically every time a new PR is [opened](https://qodo-merge-docs.qodo.ai/usage-guide/automations_and_usage/#github-app-automatic-tools-when-a-new-pr-is-opened), or in a [push](https://qodo-merge-docs.qodo.ai/usage-guide/automations_and_usage/?h=push#github-app-automatic-tools-for-push-actions-commits-to-an-open-pr) event to an existing PR.

To run the `compliance` tool automatically when a PR is opened, define the following in the [configuration file](https://qodo-merge-docs.qodo.ai/usage-guide/configuration_options/):

```toml
[github_app]  # for example
pr_commands = [
    "/compliance",
    ...
]

```

## Compliance Categories

The compliance tool evaluates three main categories:


### 1. Security Compliance

Scans for security vulnerabilities and potential exploits in the PR code changes:

- **Verified Security Concerns** 🔴: Clear security vulnerabilities that require immediate attention
- **Possible Security Risks** ⚪: Potential security issues that need human verification
- **No Security Concerns** 🟢: No security vulnerabilities were detected

Examples of security issues:

- Exposure of sensitive information (API keys, passwords, secrets)
- SQL injection vulnerabilities
- Cross-site scripting (XSS) risks
- Cross-site request forgery (CSRF) vulnerabilities
- Insecure data handling patterns


### 2. Ticket Compliance

???+ tip "How to set up ticket compliance"
    Follow the guide on how to set up [ticket compliance](https://qodo-merge-docs.qodo.ai/core-abilities/fetching_ticket_context/) with Qodo Merge.

Validates that PR changes fulfill the requirements specified in linked tickets:

- **Fully Compliant** 🟢: All ticket requirements are satisfied
- **Partially Compliant** 🟡: Some requirements are met, others need attention
- **Not Compliant** 🔴: Clear violations of ticket requirements
- **Requires Verification** ⚪: Requirements that need human review


### 3. Custom Compliance

Validates against an organization-specific compliance checklist:

- **Fully Compliant** 🟢: All custom compliance are satisfied
- **Not Compliant** 🔴: Violations of custom compliance
- **Requires Verification** ⚪: Compliance that need human assessment

## Custom Compliance

### Setting Up Custom Compliance

Each compliance is defined in a YAML file, as follows:
- `title`: Used to provide a clear name for the compliance
- `compliance_label`: Used  to automatically generate labels for non-compliance issues
- `objective`, `success_criteria`, and `failure_criteria`: These fields are used to clearly define what constitutes compliance

???+ tip "Example of a compliance checklist"

    ```yaml
    # pr_compliance_checklist.yaml
    pr_compliances:
      - title: "Error Handling"
        compliance_label: true
        objective: "All external API calls must have proper error handling"
        success_criteria: "Try-catch blocks around external calls with appropriate logging"
        failure_criteria: "External API calls without error handling or logging"
      
    ...
    ```

???+ tip "Writing effective compliance checklist"
    - Avoid overly complex or subjective compliances that are hard to verify
    - Keep compliances focused on security, business requirements, and critical standards
    - Use clear, actionable language that developers can understand
    - Focus on meaningful compliance requirements, not style preferences


### Global Hierarchical Compliance

Qodo Merge supports hierarchical compliance checklists using a dedicated global configuration repository.

#### Setting up global hierarchical compliance

1\. Create a new repository named `pr-agent-settings` in your organization/workspace.

2\. Build the folder hierarchy in your `pr-agent-settings` repository:

```bash
pr-agent-settings/
├── metadata.yaml                              # Maps repos/folders to compliance paths
└── compliance_standards/                      # Root for all compliance definitions
    ├── global/                                # Global compliance, inherited widely
    │   └── pr_compliance_checklist.yaml
    ├── groups/                                # For groups of repositories
    │   ├── frontend_repos/
    │   │   └── pr_compliance_checklist.yaml
    │   └── backend_repos/
    │   └── pr_compliance_checklist.yaml
    ├── qodo-merge/                            # For standalone repositories
    │   └── pr_compliance_checklist.yaml
    └── qodo-monorepo/                         # For monorepo-specific compliance
        ├── pr_compliance_checklist.yaml       # Root level monorepo compliance
        ├── qodo-github/                          # Subproject compliance
        │   └── pr_compliance_checklist.yaml
        └── qodo-gitlab/                           # Another subproject
            └── pr_compliance_checklist.yaml
```

3\. Define the metadata file `metadata.yaml` in the `pr-agent-settings` root:

```yaml
# Standalone repos
qodo-merge:
  pr_compliance_checklist_paths:
    - "qodo-merge"

# Group-associated repos
repo_b:
  pr_compliance_checklist_paths:
    - "groups/backend_repos"

# Multi-group repos
repo_c:
  pr_compliance_checklist_paths:
    - "groups/frontend_repos"
    - "groups/backend_repos"

# Monorepo with subprojects
qodo-monorepo:
  pr_compliance_checklist_paths:
    - "qodo-monorepo"
  monorepo_subprojects:
    frontend:
      pr_compliance_checklist_paths:
        - "qodo-monorepo/qodo-github"
    backend:
      pr_compliance_checklist_paths:
        - "qodo-monorepo/qodo-gitlab"
```

4\. Set the following configuration:

```toml
[pr_compliance]
enable_global_pr_compliance = true
```

???- info "Compliance priority and fallback behavior"

    1\. **Primary**: Global hierarchical compliance checklists from the `pr-agent-settings` repository:
    
        1.1 If the repository is mapped in `metadata.yaml`, it uses the specified paths
    
        1.2 For monorepos, it automatically collects compliance checklists matching PR file paths
    
        1.3 If no mapping exists, it falls back to the global compliance checklists

    2. **Fallback**: Local repository wiki `pr_compliance_checklist.yaml` file:

        2.1 Used when global compliance checklists are not found or configured

        2.2 Acts as a safety net for repositories not yet configured in the global system

        2.3 Local wiki compliance checklists are completely ignored when compliance checklists are successfully loaded


## Configuration Options

???+ example "General options"

    <table>
      <tr>
        <td><b>extra_instructions</b></td>
        <td>Optional extra instructions for the tool. For example: "focus on the changes in the file X. Ignore changes in ...". Default is empty string.</td>
      </tr>
      <tr>
        <td><b>persistent_comment</b></td>
        <td>If set to true, the compliance comment will be persistent, meaning that every new compliance request will edit the previous one. Default is true.</td>
      </tr>
      <tr>
        <td><b>enable_user_defined_compliance_labels</b></td>
        <td>If set to true, the tool will add labels for custom compliance violations. Default is true.</td>
      </tr>
      <tr>
        <td><b>enable_estimate_effort_to_review</b></td>
        <td>If set to true, the tool will estimate the effort required to review the PR (1-5 scale). Default is true.</td>
      </tr>
      <tr>
        <td><b>enable_todo_scan</b></td>
        <td>If set to true, the tool will scan for TODO comments in the PR code. Default is false.</td>
      </tr>
      <tr>
        <td><b>enable_update_pr_compliance_checkbox</b></td>
        <td>If set to true, the tool will add an update checkbox to refresh compliance status. Default is true.</td>
      </tr>
      <tr>
        <td><b>enable_help_text</b></td>
        <td>If set to true, the tool will display a help text in the comment. Default is false.</td>
      </tr>
    </table>

???+ example "Security compliance options"

    <table>
      <tr>
        <td><b>enable_security_compliance</b></td>
        <td>If set to true, the tool will check for security vulnerabilities. Default is true.</td>
      </tr>
      <tr>
        <td><b>enable_compliance_labels_security</b></td>
        <td>If set to true, the tool will add security-related labels to the PR. Default is true.</td>
      </tr>
    </table>

???+ example "Ticket compliance options"

    <table>
      <tr>
        <td><b>enable_ticket_labels</b></td>
        <td>If set to true, the tool will add ticket compliance labels to the PR. Default is false.</td>
      </tr>
      <tr>
        <td><b>enable_no_ticket_labels</b></td>
        <td>If set to true, the tool will add a label when no ticket is found. Default is false.</td>
      </tr>
      <tr>
        <td><b>check_pr_additional_content</b></td>
        <td>If set to true, the tool will check if the PR contains content not related to the ticket. Default is false.</td>
      </tr>
    </table>


## Usage Tips

### Blocking PRs Based on Compliance

!!! tip ""
    You can configure CI/CD Actions to prevent merging PRs with specific compliance labels:
    
    - `Possible security concern` - Block PRs with potential security issues
    - `Failed compliance check` - Block PRs that violate custom compliance checklists
    
    Implement a dedicated [GitHub Action](https://medium.com/sequra-tech/quick-tip-block-pull-request-merge-using-labels-6cc326936221) to enforce these checklists.

