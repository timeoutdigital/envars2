# Envars: Application Config as Code

[![PyPI version](https://badge.fury.io/py/envars.svg)](https://badge.fury.io/py/envars)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Envars** is a powerful command-line tool for managing your application's configuration as code. It provides a simple yet flexible way to handle environment variables across different applications, environments, and cloud providers, ensuring that your configuration is always consistent, secure, and easy to manage.

Stop juggling `.env` files and start treating your configuration like code.

## Key Features

- **Configuration as Code**: Store your entire configuration in a single, version-controlled `envars.yml` file.
- **Hierarchical Configuration**: Define variables at different levels (default, environment, location) and let `envars` resolve the correct value for the context.
- **Secure Secret Management**: Encrypt and decrypt sensitive values using [AWS KMS](https://aws.amazon.com/kms/) or [Google Cloud KMS](https://cloud.google.com/kms).
- **Templating with Jinja2**: Resolve variable values dynamically using the power of Jinja2 templating.
- **Value Validation**: Ensure the integrity of your configuration with optional regex-based validation for variable values.
- **Cloud Secret Manager Integration**: Fetch secrets on-the-fly from [AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html) or [GCP Secret Manager](https://cloud.google.com/secret-manager).
- **Powerful CLI**: A rich set of commands for initializing, adding, printing, validating, and executing your configuration.

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

### `print`

Prints the resolved variables for a given context.

```bash
envars print --env dev --loc aws
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
```

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
