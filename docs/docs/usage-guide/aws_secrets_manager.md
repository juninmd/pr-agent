# AWS Secrets Manager Integration

Securely manage sensitive information such as API keys and webhook secrets when running PR-Agent in AWS Lambda environments.

## Overview

AWS Secrets Manager integration allows you to:

- Store sensitive configuration in AWS Secrets Manager instead of environment variables
- Automatically retrieve and apply secrets at application startup
- Improve security for Lambda deployments
- Centrally manage secrets across multiple environments

## Prerequisites

- AWS Lambda deployment of PR-Agent
- AWS Secrets Manager access permissions
- Boto3 library (already included in PR-Agent dependencies)

## Configuration

### Step 1: Create Secret in AWS Secrets Manager

Create a secret in AWS Secrets Manager with JSON format:

```json
{
  "openai.key": "sk-...",
  "github.webhook_secret": "your-webhook-secret",
  "github.user_token": "ghp_...",
  "gitlab.personal_access_token": "glpat-..."
}
```

### Step 2: Configure PR-Agent

Add the following to your configuration:

```toml
# configuration.toml
[config]
secret_provider = "aws_secrets_manager"

# .secrets.toml or environment variables
[aws_secrets_manager]
secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:pr-agent-secrets-AbCdEf"
region_name = ""  # Optional: specific region (defaults to Lambda's region)
```

### Step 3: Set IAM Permissions

Your Lambda execution role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:region:account:secret:pr-agent/*"
    }
  ]
}
```

## Environment Variable Mapping

Secrets Manager keys should use dot notation that maps to configuration sections:

| Secret Key              | Configuration Section | Environment Variable     |
| ----------------------- | --------------------- | ------------------------ |
| `openai.key`            | `[openai]`            | `OPENAI__KEY`            |
| `github.webhook_secret` | `[github]`            | `GITHUB__WEBHOOK_SECRET` |
| `github.user_token`     | `[github]`            | `GITHUB__USER_TOKEN`     |

## Fallback Behavior

If AWS Secrets Manager is unavailable or misconfigured:

- PR-Agent will fall back to environment variables
- A debug log message will be recorded
- No service interruption occurs

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure Lambda execution role has `secretsmanager:GetSecretValue` permission
2. **Secret Not Found**: Verify the secret ARN is correct and exists in the specified region
3. **JSON Parse Error**: Ensure the secret value is valid JSON format
4. **Connection Issues**: Check network connectivity and AWS region settings

### Debug Logging

Enable debug logging to troubleshoot:

```toml
[config]
log_level = "DEBUG"
```

Check CloudWatch logs for warning/error messages related to AWS Secrets Manager access.

## Security Best Practices

1. Use least-privilege IAM policies
2. Rotate secrets regularly
3. Use separate secrets for different environments
4. Monitor CloudTrail for secret access
5. Enable secret versioning for rollback capability
