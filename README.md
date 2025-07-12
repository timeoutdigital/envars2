# Envars: Application Config as Code TEST

[![PyPI version](https://badge.fury.io/py/envars2.svg)](https://badge.fury.io/py/envars2)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Envars** is a powerful command-line tool for managing your application's configuration as code. It provides a simple yet flexible way to handle environment variables across different applications, environments, and cloud providers, ensuring that your configuration is always consistent, secure, and easy to manage.

Stop juggling `.env` files and start treating your configuration like code.

## Key Features

- **Configuration as Code**: Store your entire configuration in a single, version-controlled `envars.yml` file.
- **Hierarchical Configuration**: Define variables at different levels (default, environment, location) and let `envars` resolve the correct value for the context.
- **Secure Secret Management**: Encrypt and decrypt sensitive values using [AWS KMS](https://aws.amazon.com/kms/) or [Google Cloud KMS](https://cloud.google.com/kms).
- **Templating with Jinja2**: Resolve variable values dynamically using the power of Jinja2 templating.
- **Value Validation**: Ensure the integrity of your configuration with optional regex-based validation for variable values.
- **Cloud Secret Manager Integration**: Fetch secrets on-the-fly from [AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html), [GCP Secret Manager](https://cloud.google.com/secret-manager), or [AWS CloudFormation Exports](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html).
- **Powerful CLI**: A rich set of commands for initializing, adding, outputting, validating, and executing your configuration.
- **Can be used as a library**: in other python apps

## Installation

```bash
pip install envars
```

## Quick Start

1.  **Initialize a new project:**
    ```bash
    envars init --app "my-app" --env "dev,prod" --loc "aws:123456789012"
    ```

2.  **Add a variable:**
    ```bash
    envars add DATABASE_URL="postgres://user:pass@localhost:5432/mydb" --description "The database connection string."
    ```

3.  **Add a secret:**
    ```bash
    envars add API_KEY="super-secret-key" --secret --env dev --loc aws
    ```

4.  **Execute a command with the environment:**
    ```bash
    envars exec --env dev --loc aws -- python my_script.py
    ```

## Usage

### `add`

Adds or updates a variable in your `envars.yml` file.

```bash
# Add a default variable
envars add MY_VAR=my_value

# Add a variable with a description and validation
envars add EMAIL="test@example.com" --description "A user's email" --validation "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

# Add a secret for a specific environment and location
envars add MY_SECRET="super-secret" --secret --env prod --loc aws
```

### `output`

Outputs the resolved variables for a given context in desired format

```bash
envars output --env dev --loc aws --format json
```

### `exec`

Executes a command with the resolved variables populated in the environment.

```bash
envars exec --env dev --loc aws -- ./my_app
```

### `validate`

Validates the `envars.yml` file for logical consistency, including circular dependencies and validation rules.

```bash
envars validate
```

## Configuration (`envars.yml`)

The `envars.yml` file is the heart of your configuration. It's a simple YAML file with two main sections: `configuration` and `environment_variables`.

```yaml
configuration:
  app: my-app
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
    - prod
  locations:
    - aws: "123456789012"
    - gcp: "my-gcp-project"

environment_variables:
  DATABASE_URL:
    description: "The database connection string."
    default: "postgres://user:pass@localhost:5432/mydb"
    prod:
      aws: "postgres://user:pass@prod-db.example.com:5432/mydb"

  API_KEY:
    description: "A 32-character hexadecimal API key."
    validation: "^[a-fA-F0-9]{32}$"
    dev:
      aws: !secret "CiD...=="
    prod:
      aws: !secret "CiD...=="

  GCP_SECRET:
    description: "A secret stored in GCP Secret Manager."
    prod:
      gcp: "gcp_secret_manager:projects/my-gcp-project/secrets/my-secret/versions/latest"

  CF_EXPORT:
    description: "A value from CloudFormation exports."
    prod:
      aws: "cloudformation_export:my-export-name"
```

## Possible Enhancements

Here are some ideas for future enhancements that could make `envars` even more powerful:

- **AWS Secrets Manager Integration**: Add a new `aws_secrets_manager:` prefix to fetch secrets directly from AWS Secrets Manager, which is a more feature-rich service for managing sensitive data than SSM Parameter Store.
- **Terraform State File Lookup**: Implement a `terraform_state:` prefix to read outputs directly from a Terraform state file (e.g., from an S3 or GCS backend). This would create a powerful, direct link between your infrastructure-as-code and application configuration.
- **HashiCorp Vault Integration**: Support for `vault:` lookups to fetch secrets from a HashiCorp Vault instance, which would make `envars` more useful in on-premise or multi-cloud environments.
- **Local File Content Lookup**: A `file:` prefix to read the content of a local file directly into a variable. This would be useful for loading certificates, keys, or other configuration files that are not suitable for storing in `envars.yml` itself.

## Development

To set up the development environment, clone the repository and install the dependencies using `uv`:

```bash
git clone https://github.com/your-username/envars.git
cd envars
uv sync
```

To run the tests:

```bash
uv run pytest
```
