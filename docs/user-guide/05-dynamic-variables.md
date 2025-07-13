# User Guide: Dynamic Variables from Cloud Providers

A powerful feature of `envars` is its ability to fetch variable values dynamically from external cloud services at runtime. This allows you to reference infrastructure outputs or secrets managed outside of `envars` without having to copy and paste them into your `envars.yml` file.

This is supported for:

*   **AWS Systems Manager Parameter Store**
*   **AWS CloudFormation Exports**
*   **GCP Secret Manager**

## How it Works

You define a variable with a special prefix. When you run `envars output` or `envars exec`, `envars` recognizes the prefix, calls the appropriate cloud provider API, and replaces the variable's value with the fetched result.

**Note:** The machine running `envars` must have the necessary cloud credentials and IAM/GCP permissions to access the requested resources.

---

## AWS Systems Manager Parameter Store

Use the `parameter_store:` prefix to fetch a value from the AWS Parameter Store.

*   **Format:** `parameter_store:/path/to/parameter`

### Example

```yaml
# In envars.yml
environment_variables:
  DATABASE_PASSWORD:
    description: "The database password, managed in Parameter Store."
    prod: "parameter_store:/myapp/prod/database_password"
```

When you run `envars output --env prod`, `envars` will call the `GetParameter` API for `/myapp/prod/database_password` and inject the returned value.

---

## AWS CloudFormation Exports

Use the `cloudformation_export:` prefix to use the value of a CloudFormation stack export.

*   **Format:** `cloudformation_export:ExportName`

### Example

Imagine a networking stack that exports the ID of a VPC.

```yaml
# In envars.yml
environment_variables:
  VPC_ID:
    description: "The VPC ID, from the networking stack."
    default: "cloudformation_export:MyNetworkStack-VPCID"
```

`envars` will call the `ListExports` API to find the value of the export named `MyNetworkStack-VPCID`.

---

## GCP Secret Manager

Use the `gcp_secret_manager:` prefix to access a secret from Google Cloud Secret Manager.

*   **Format:** `gcp_secret_manager:projects/my-project/secrets/my-secret/versions/latest`

### Example

```yaml
# In envars.yml
environment_variables:
  GOOGLE_API_KEY:
    description: "The API key for Google services."
    prod: "gcp_secret_manager:projects/my-gcp-proj/secrets/google-api-key/versions/latest"
```

`envars` will call the `accessSecretVersion` API to fetch the secret's payload.

## Templating with Dynamic Variables

You can combine dynamic variables with [Variable Templating](./04-variable-templating.md) for even more power.

### Example

```yaml
# In envars.yml
environment_variables:
  SECRET_NAME:
    prod: "prod-database-password"
    dev: "dev-database-password"

  DATABASE_PASSWORD:
    # The path to the secret is now dynamic based on the environment
    default: "gcp_secret_manager:projects/my-proj/secrets/{{ SECRET_NAME }}/versions/1"
```

In this example, `envars` will first resolve `SECRET_NAME` based on the environment, and *then* it will use the result to construct the full path to fetch from GCP Secret Manager.
