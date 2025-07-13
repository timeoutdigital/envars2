# User Guide: The `envars.yml` File

The `envars.yml` file is the heart of the `envars` system. It's a YAML file designed to be a single source of truth for all your application's environment variables. This guide provides a detailed breakdown of its structure.

## Top-Level Structure

The file has two main sections: `configuration` and `environment_variables`.

```yaml
configuration:
  # ... global settings ...

environment_variables:
  # ... variable definitions ...
```

---

## The `configuration` Section

This section defines the global settings for your project, including metadata, environments, and locations.

### `app`

A string that identifies your application. This is used as a context for secret encryption.

*   **Type:** `string`
*   **Example:** `app: MyWebApp`

### `kms_key`

The full ARN (for AWS) or resource name (for GCP) of the KMS key used to encrypt and decrypt secrets.

*   **Type:** `string`
*   **Example (AWS):** `kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"`
*   **Example (GCP):** `kms_key: "projects/my-proj/locations/global/keyRings/my-ring/cryptoKeys/my-key"`

### `description_mandatory`

A boolean that, if `true`, requires a `description` to be provided for every new variable.

*   **Type:** `boolean`
*   **Default:** `false`
*   **Example:** `description_mandatory: true`

### `environments`

A list of strings defining the different environments your application runs in (e.g., `dev`, `staging`, `prod`).

*   **Type:** `list` of `string`
*   **Example:**
    ```yaml
    environments:
      - dev
      - prod
      - staging
    ```

### `locations`

A list of mappings that define the different locations where your application is deployed. A location typically corresponds to an AWS account or a GCP project.

*   **Type:** `list` of `mappings`
*   **Format:** `name: id`
*   **Example:**
    ```yaml
    locations:
      - aws-dev: "123456789012"
      - aws-prod: "987654321098"
      - gcp-main: "my-gcp-project-id"
    ```

---

## The `environment_variables` Section

This section contains the definitions for all your variables. Each key under `environment_variables` is a variable name, which must be in `UPPERCASE`.

### Variable Definition

Each variable is an object with the following optional keys:

*   `description`: A human-readable description of the variable.
*   `validation`: A regex pattern to validate the variable's value against.
*   `default`: The default value for the variable.
*   **Environment Overrides:** Keys matching a name in `environments`.
*   **Location Overrides:** Keys matching a name in `locations`.

### Value Hierarchy

`envars` uses a clear hierarchy to determine which value to use. The most specific value always wins. The order of precedence is:

1.  **Specific Value:** A value defined for both an environment and a location.
2.  **Environment Value:** A value defined for an environment.
3.  **Location Value:** A value defined for a location.
4.  **Default Value:** The fallback value.

### Examples

#### A Simple Variable with Overrides

```yaml
environment_variables:
  LOG_LEVEL:
    description: "The application log level."
    default: "INFO"
    prod: "WARN" # Overrides the default in the 'prod' environment
```

#### A Secret Variable

Use the `!secret` tag to mark a value as a secret. It will be encrypted before being saved.

```yaml
environment_variables:
  API_KEY:
    description: "API key for the external service."
    prod: !secret "super-secret-value"
```

#### A Variable with Location and Environment Overrides

```yaml
environment_variables:
  API_ENDPOINT:
    description: "The API endpoint to connect to."
    default: "https://api.example.com"
    aws-prod: "https://api.prod.aws.example.com" # Location-specific
    dev:
      aws-dev: "https://api.dev.aws.example.com" # Specific to dev and aws-dev
```
