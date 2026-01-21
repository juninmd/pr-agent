<img width="697" height="176" alt="image" src="https://github.com/user-attachments/assets/81c96bcc-4ec3-45b2-a69e-d116bb75b22b" />

<a href="https://github.com/Codium-ai/pr-agent/commits/main">
<img alt="GitHub" src="https://img.shields.io/github/last-commit/Codium-ai/pr-agent/main?style=for-the-badge" height="20">
</a>

<br />

# 🚀 O Primeiro Revisor de Código com IA

O PR-Agent é um agente de revisão de código open-source alimentado por IA e um projeto legado mantido pela comunidade da Qodo. Ele é distinto da oferta principal de revisão de código com IA da Qodo, que oferece uma experiência rica em recursos e ciente do contexto. A Qodo agora oferece um nível gratuito que se integra perfeitamente ao GitHub, GitLab, Bitbucket e Azure DevOps para revisões automatizadas de alta qualidade.

## Índice

- [Começando](#começando)
- [Por que usar o PR-Agent?](#por-que-usar-o-pr-agent)
- [Funcionalidades](#funcionalidades)
- [Veja em Ação](#veja-em-ação)
- [Experimente Agora](#experimente-agora)
- [Como Funciona](#como-funciona)
- [Privacidade de Dados](#privacidade-de-dados)
- [Contribuindo](#contribuindo)

## Começando

### 🚀 Começo Rápido para o PR-Agent

#### 1. Experimente Instantaneamente (Sem Configuração)
Teste o PR-Agent em qualquer repositório público do GitHub comentando `@CodiumAI-Agent /improve`

#### 2. GitHub Action (Recomendado)
Adicione revisões automáticas de PR ao seu repositório com um arquivo de fluxo de trabalho simples:
```yaml
# .github/workflows/pr-agent.yml
name: PR Agent
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  pr_agent_job:
    runs-on: ubuntu-latest
    steps:
    - name: PR Agent action step
      uses: Codium-ai/pr-agent@main
      env:
        OPENAI_KEY: ${{ secrets.OPENAI_KEY }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
[Guia completo de configuração do GitHub Action](https://qodo-merge-docs.qodo.ai/installation/github/#run-as-a-github-action)

#### 3. Uso via CLI (Desenvolvimento Local)
Execute o PR-Agent localmente em seu repositório:
```bash
pip install pr-agent
export OPENAI_KEY=sua_chave_aqui
pr-agent --pr_url https://github.com/owner/repo/pull/123 review
```
[Guia completo de configuração da CLI](https://qodo-merge-docs.qodo.ai/usage-guide/automations_and_usage/#local-repo-cli)

#### 4. Outras Plataformas
- [Configuração de webhook do GitLab](https://qodo-merge-docs.qodo.ai/installation/gitlab/)
- [Instalação do aplicativo BitBucket](https://qodo-merge-docs.qodo.ai/installation/bitbucket/)
- [Configuração do Azure DevOps](https://qodo-merge-docs.qodo.ai/installation/azure/)

[//]: # (## Notícias e Atualizações - Comentadas no original)

## Por que usar o PR-Agent?

### 🎯 Construído para Equipes de Desenvolvimento Reais

**Rápido e Acessível**: Cada ferramenta (`/review`, `/improve`, `/ask`) usa uma única chamada LLM (~30 segundos, baixo custo).

**Lida com Qualquer Tamanho de PR**: Nossa [Estratégia de Compressão de PR](https://qodo-merge-docs.qodo.ai/core-abilities/#pr-compression-strategy) processa efetivamente tanto PRs pequenos quanto grandes.

**Altamente Personalizável**: Prompting baseado em JSON permite fácil personalização de categorias de revisão e comportamento via [arquivos de configuração](pr_agent/settings/configuration.toml).

**Agnóstico de Plataforma**:
- **Provedores Git**: GitHub, GitLab, BitBucket, Azure DevOps, Gitea
- **Implantação**: CLI, GitHub Actions, Docker, auto-hospedado, webhooks
- **Modelos de IA**: OpenAI GPT, Claude, Deepseek e mais

**Benefícios Open Source**:
- Controle total sobre seus dados e infraestrutura
- Personalize prompts e comportamento para as necessidades da sua equipe
- Sem bloqueio de fornecedor (Vendor lock-in)
- Desenvolvimento impulsionado pela comunidade

## Funcionalidades

<div style="text-align:left;">

O PR-Agent oferece funcionalidades abrangentes de pull request integradas com vários provedores git:

|                                                         |                                                                                        | GitHub | GitLab | Bitbucket | Azure DevOps | Gitea |
|---------------------------------------------------------|----------------------------------------------------------------------------------------|:------:|:------:|:---------:|:------------:|:-----:|
| [FERRAMENTAS](https://qodo-merge-docs.qodo.ai/tools/)   | [Describe (Descrever)](https://qodo-merge-docs.qodo.ai/tools/describe/)               |   ✅   |   ✅   |    ✅     |      ✅      |  ✅   |
|                                                         | [Review (Revisar)](https://qodo-merge-docs.qodo.ai/tools/review/)                      |   ✅   |   ✅   |    ✅     |      ✅      |  ✅   |
|                                                         | [Improve (Melhorar)](https://qodo-merge-docs.qodo.ai/tools/improve/)                   |   ✅   |   ✅   |    ✅     |      ✅      |  ✅   |
|                                                         | [Ask (Perguntar)](https://qodo-merge-docs.qodo.ai/tools/ask/)                          |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | ⮑ [Perguntar nas linhas de código](https://qodo-merge-docs.qodo.ai/tools/ask/#ask-lines)|   ✅   |   ✅   |           |              |       |
|                                                         | [Help Docs](https://qodo-merge-docs.qodo.ai/tools/help_docs/?h=auto#auto-approval)     |   ✅   |   ✅   |    ✅     |              |       |
|                                                         | [Atualizar CHANGELOG](https://qodo-merge-docs.qodo.ai/tools/update_changelog/)         |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         |                                                                                        |        |        |           |              |       |
| [USO](https://qodo-merge-docs.qodo.ai/usage-guide/)     | [CLI](https://qodo-merge-docs.qodo.ai/usage-guide/automations_and_usage/#local-repo-cli)|   ✅   |   ✅   |    ✅     |      ✅      |  ✅   |
|                                                         | [App / webhook](https://qodo-merge-docs.qodo.ai/usage-guide/automations_and_usage/#github-app)|   ✅   |   ✅   |    ✅     |      ✅      |  ✅   |
|                                                         | [Bot de marcação](https://github.com/Codium-ai/pr-agent#try-it-now)                    |   ✅   |        |           |              |       |
|                                                         | [Actions](https://qodo-merge-docs.qodo.ai/installation/github/#run-as-a-github-action) |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         |                                                                                        |        |        |           |              |       |
| [NÚCLEO](https://qodo-merge-docs.qodo.ai/core-abilities/)| [Ajuste de patch de arquivo adaptável e ciente de tokens](https://qodo-merge-docs.qodo.ai/core-abilities/compression_strategy/) |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | [Chat em sugestões de código](https://qodo-merge-docs.qodo.ai/core-abilities/chat_on_code_suggestions/)                |   ✅   |  ✅   |           |              |       |
|                                                         | [Contexto dinâmico](https://qodo-merge-docs.qodo.ai/core-abilities/dynamic_context/)                                  |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | [Busca de contexto de ticket](https://qodo-merge-docs.qodo.ai/core-abilities/fetching_ticket_context/)                  |   ✅    |  ✅    |     ✅     |              |       |
|                                                         | [Atualização Incremental](https://qodo-merge-docs.qodo.ai/core-abilities/incremental_update/)                            |   ✅    |       |           |              |       |
|                                                         | [Interatividade](https://qodo-merge-docs.qodo.ai/core-abilities/interactivity/)                                      |   ✅   |  ✅   |           |              |       |
|                                                         | [Metadados locais e globais](https://qodo-merge-docs.qodo.ai/core-abilities/metadata/)                               |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | [Suporte a múltiplos modelos](https://qodo-merge-docs.qodo.ai/usage-guide/changing_a_model/)                            |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | [Compressão de PR](https://qodo-merge-docs.qodo.ai/core-abilities/compression_strategy/)                              |   ✅   |   ✅   |    ✅     |      ✅      |       |
|                                                         | [Enriquecimento de contexto RAG](https://qodo-merge-docs.qodo.ai/core-abilities/rag_context_enrichment/)                    |   ✅    |       |    ✅     |              |       |
|                                                         | [Auto-reflexão](https://qodo-merge-docs.qodo.ai/core-abilities/self_reflection/)                                  |   ✅   |   ✅   |    ✅     |      ✅      |       |

___

## Veja em Ação

</div>
<h4><a href="https://github.com/Codium-ai/pr-agent/pull/530">/describe</a></h4>
<div align="center">
<p float="center">
<img src="https://www.codium.ai/images/pr_agent/describe_new_short_main.png" width="512">
</p>
</div>
<hr>

<h4><a href="https://github.com/Codium-ai/pr-agent/pull/732#issuecomment-1975099151">/review</a></h4>
<div align="center">
<p float="center">
<kbd>
<img src="https://www.codium.ai/images/pr_agent/review_new_short_main.png" width="512">
</kbd>
</p>
</div>
<hr>

<h4><a href="https://github.com/Codium-ai/pr-agent/pull/732#issuecomment-1975099159">/improve</a></h4>
<div align="center">
<p float="center">
<kbd>
<img src="https://www.codium.ai/images/pr_agent/improve_new_short_main.png" width="512">
</kbd>
</p>
</div>

<div align="left">

</div>
<hr>

## Experimente Agora

Experimente o PR-Agent alimentado por GPT-5 instantaneamente em *seu repositório público do GitHub*. Apenas mencione `@CodiumAI-Agent` e adicione o comando desejado em qualquer comentário de PR. O agente gerará uma resposta com base no seu comando.
Por exemplo, adicione um comentário a qualquer pull request com o seguinte texto:

```
@CodiumAI-Agent /review
```

e o agente responderá com uma revisão do seu PR.

Note que este é um bot promocional, adequado apenas para experimentação inicial.
Ele não tem acesso de 'edição' ao seu repositório, por exemplo, então ele não pode atualizar a descrição do PR ou adicionar rótulos (`@CodiumAI-Agent /describe` publicará a descrição do PR como um comentário). Além disso, o bot não pode ser usado em repositórios privados, pois não tem acesso aos arquivos lá.


## Como Funciona

O diagrama a seguir ilustra as ferramentas do PR-Agent e seu fluxo:

![Ferramentas PR-Agent](https://www.qodo.ai/images/pr_agent/diagram-v0.9.png)

## Privacidade de Dados

### PR-Agent Auto-hospedado

- Se você hospedar o PR-Agent com sua chave de API da OpenAI, isso é entre você e a OpenAI. Você pode ler a política de privacidade de dados da API deles aqui:
https://openai.com/enterprise-privacy

## Contribuindo

Para contribuir com o projeto, comece lendo nosso [Guia de Contribuição](https://github.com/qodo-ai/pr-agent/blob/b09eec265ef7d36c232063f76553efb6b53979ff/CONTRIBUTING.md).


## ❤️ Comunidade

Este lançamento open-source permanece aqui como uma contribuição da comunidade da Qodo — a origem da colaboração de código moderna alimentada por IA. Estamos orgulhosos de compartilhá-lo e inspirar desenvolvedores em todo o mundo.

O projeto agora tem seu primeiro mantenedor externo, Naor ([@naorpeled](https://github.com/naorpeled)), e está atualmente no processo de ser doado para uma fundação open-source.
