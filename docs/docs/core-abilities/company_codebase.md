# Company Codebase 💎
`Supported Git Platforms: GitHub`


## Overview

### What is Company Codebase?

An organized, semantic database that aggregates all your company’s source code into one searchable repository, enabling efficient code discovery and analysis.

### How does Company Codebase work?

By indexing your company's code and using Retrieval-Augmented Generation (RAG), it retrieves contextual code segments on demand, improving pull request (PR) insights and accelerating review accuracy.


## Getting started

!!! info "Prerequisites"
    - Database setup and codebase indexing must be completed before proceeding. [Contact support](https://www.qodo.ai/contact/) for assistance.

### Configuration options

In order to enable the RAG feature, add the following lines to your configuration file:
``` toml
[rag_arguments]
enable_rag=true 
```

!!! example "RAG Arguments Options"

    <table>
      <tr>
        <td><b>enable_rag</b></td>
        <td>If set to true, codebase enrichment using RAG will be enabled. Default is false.</td>
      </tr>
      <tr>
        <td><b>rag_repo_list</b></td>
        <td>A list of repositories that will be used by the semantic search for RAG. Use `['all']` to consider the entire codebase or a select list or repositories, for example: ['my-org/my-repo', ...]. Default: the repository from which the PR was opened.</td>
      </tr>
    </table>


References from the codebase will be shown in a collapsible bookmark, allowing you to easily access relevant code snippets:

![References](https://codium.ai/images/pr_agent/company_codebase_references.png){width=640}

## Limitations

### Querying the codebase presents significant challenges:
- **Search Method**: RAG uses natural language queries to find semantically relevant code sections
- **Result Quality**: No guarantee that RAG results will be useful for all queries
- **Scope Recommendation**: To reduce noise, avoid using the whole codebase; focus on PR repository instead

### This feature has several requirements and restrictions:
- **Codebase**: Must be properly indexed for search functionality
- **Security**: Requires secure and private indexed codebase implementation
- **Deployment**: Only available for Qodo Merge Enterprise plan using single tenant or on-premises setup
