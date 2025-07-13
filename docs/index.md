# Envars: Application Config as Code

**Tired of managing environment variables across different environments and cloud providers? `envars` is a command-line tool that brings sanity to your application configuration.**

`envars` allows you to define all your environment variables—for different environments (`dev`, `staging`, `prod`) and locations (AWS accounts, GCP projects)—in a single, version-controlled `envars.yml` file.

## Key Features

*   **Centralized Configuration:** A single source of truth for all your environment variables.
*   **Hierarchical Overrides:** Define default values and override them for specific environments or locations.
*   **Secret Management:** Natively encrypt and decrypt secrets using AWS KMS or GCP KMS.
*   **Dynamic Variables:** Fetch values on-the-fly from AWS Parameter Store, AWS CloudFormation Exports, or GCP Secret Manager.
*   **Validation:** Ensure variables conform to expected formats with regex validation.
*   **Templating:** Use Jinja2 templating to create dynamic variables based on other variables.

## A Quick Look

Here's a simple `envars.yml` file:

```yaml
configuration:
  app: MyWebApp
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
    - prod
  locations:
    - aws-dev: "123456789012"
    - aws-prod: "987654321098"

environment_variables:
  LOG_LEVEL:
    description: "The logging level for the application."
    default: "INFO"
    prod: "WARN"

  API_KEY:
    description: "The API key for the external service."
    dev: "dev-key"
    prod: !secret "CiD...encrypted-blob...=="

  DATABASE_URL:
    description: "The connection string for the database."
    default: "postgres://user:pass@db-{{ env.get('STAGE') }}.example.com/mydb"
```

With this file, you can easily export the variables for a specific context:

```bash
$ envars output --env dev --loc aws-dev
LOG_LEVEL=INFO
API_KEY=dev-key
DATABASE_URL=postgres://user:pass@db-dev.example.com/mydb
```

Ready to simplify your configuration management? **[Get Started](getting-started.md)**