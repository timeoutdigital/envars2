# Envars2: Environment Variable Management CLI

Envars2 is a powerful command-line tool for managing environment variables across different applications, environments (e.g., `dev`, `prod`), and locations (e.g., `aws`, `gcp`). It helps you maintain a single source of truth for your configuration, supports encryption for sensitive data, and provides flexible commands for various workflows.

## Key Features

- **Centralized Configuration**: Manage all your environment variables in a single `envars.yml` file.
- **Hierarchical Scopes**: Define variables at different levels (default, environment, location, or specific combinations) and let the tool resolve the correct value based on the context.
- **Secrets Management**: Encrypt and decrypt sensitive values using AWS KMS or Google Cloud KMS. Envars2 uses encryption contexts, which means you can use IAM policies to control who can decrypt secrets for a specific environment and location.
- **Flexible Commands**:
  - `init`: Initialize a new `envars.yml` file.
  - `add`: Add or update variables.
  - `config`: Update the configuration.
  - `print`: Display resolved variables in different formats.
  - `exec`: Execute a command with the resolved environment variables.
  - `yaml`: Output resolved variables as a YAML object.
  - `set-systemd-env`: Set environment variables for a systemd user service.
  - `validate`: Validate the `envars.yml` file for logical consistency.
- **Shell Integration**: Use the `STAGE` environment variable to set the default environment for the `exec`, `yaml`, and `set-systemd-env` commands.
- **Strict Validation**: Enforces uppercase variable names and correct structure.
- **Safety Features**: Warns you when you might be adding a sensitive variable without encryption and requires you to be explicit.

## Philosophy: Configuration as Code

By storing the environment configuration for all environments in the application's repository, `envars2` allows you to treat your configuration as code. This has several benefits:

- **Visibility:** Changes to the environment that are required for a code change can be included in the same commit. This improves visibility and makes it easier to understand the history of your application's configuration.
- **Consistency:** All environments are defined in the same file, which helps to ensure consistency and reduce the risk of configuration drift between environments.
- **Automation:** The `envars.yml` file can be used to automate the deployment of your application, ensuring that the correct environment variables are always set for each environment.

## Installation

To install Envars2, you can use pip:

```bash
pip install .
```

## Configuration (`envars.yml`)

The `envars.yml` file is the heart of the tool. It has two main sections: `configuration` and `environment_variables`.

### `configuration`

This section defines the overall settings for your project:

- `app`: (Optional) The name of your application.
- `kms_key`: (Optional) The global KMS key to use for encryption. This can be an AWS KMS key ARN or a Google Cloud KMS key resource name.
- `environments`: A list of the environments you want to manage (e.g., `dev`, `prod`).
- `locations`: A list of the locations where your application runs. Each location has a name and an ID. You can also specify a location-specific KMS key.

### `environment_variables`

This section defines your environment variables. Each variable can have a `description` and a `default` value. You can then override the default value for specific environments, locations, or combinations of both.

Here's a complete example of an `envars.yml` file:

```yaml
configuration:
  app: "my-app"
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - "dev"
    - "prod"
  locations:
    - aws: "123456789012"
    - gcp: "projects/my-gcp-project"

environment_variables:
  API_KEY:
    description: "API key for a third-party service."
    default: "default-key"
    dev: "dev-key"
    prod:
      aws: !secret "encrypted-aws-key"
      gcp: !secret "encrypted-gcp-key"

  DB_HOST:
    description: "Database host."
    default: "localhost"
    prod: "db.my-app.com"

  DEBUG:
    description: "Enable debug mode."
    default: "false"
    dev: "true"
```

### Templating with Jinja2

Envars2 uses the Jinja2 templating engine, which allows you to create dynamic and reusable variable definitions. You can reference other variables and even shell environment variables in your `envars.yml` file.

**Referencing Other Variables:**

You can reference other variables using the `{{ VARIABLE_NAME }}` syntax.

```yaml
environment_variables:
  DOMAIN:
    default: "example.com"
  HOSTNAME:
    default: "my-app.{{ DOMAIN }}"
```

**Referencing Shell Environment Variables:**

You can access shell environment variables using the `env` object. It's recommended to use the `.get()` method to provide a default value in case the shell variable is not set.

```yaml
environment_variables:
  SENTRY_DSN:
    default: "https://{{ env.get('SENTRY_KEY') }}@sentry.io/12345"
  PORT:
    default: "{{ env.get('PORT', 5000) }}"
```

### Referencing AWS Parameter Store

You can also reference secrets stored in AWS Systems Manager Parameter Store. This is useful when you have a variable that is shared between multiple applications.

To do this, use the `parameter_store:` prefix followed by the name of the parameter.

```yaml
environment_variables:
  SHARED_SECRET:
    default: "parameter_store:/shared/secret"
```

### Referencing GCP Secret Manager

Similarly, you can reference secrets stored in Google Cloud Secret Manager.

To do this, use the `gcp_secret_manager:` prefix followed by the full resource name of the secret version.

```yaml
environment_variables:
  GCP_SECRET:
    default: "gcp_secret_manager:projects/my-project/secrets/my-secret/versions/latest"
```

## Usage

### `init`

Initialize a new `envars.yml` file.

**Syntax:**

```bash
envars2 init --app <app_name> --env <env1,env2> --loc <loc1:id1,loc2:id2> [OPTIONS]
```

**Example:**

```bash
envars2 init --app "my-app" --env "dev,prod" --loc "aws:123,gcp:456"
```

### `add`

Add or update an environment variable.

**Syntax:**

```bash
envars2 add <VAR=value> [OPTIONS]
```

**Examples:**

- Add a default value:
  ```bash
  envars2 add MY_VAR=default_value
  ```
- Add a value for a specific environment:
  ```bash
  envars2 add MY_VAR=dev_value --env dev
  ```
- Add an encrypted secret:
  ```bash
  envars2 add MY_SECRET=super_secret --secret
  ```
- Add a sensitive variable as plaintext:
  ```bash
  envars2 add MY_PASSWORD=not_a_secret --no-secret
  ```

### `config`

Update the configuration in the `envars.yml` file.

**Syntax:**

```bash
envars2 config [OPTIONS]
```

**Example:**

```bash
envars2 config --kms-key new-kms-key --add-env test --remove-loc gcp --description-mandatory
```

### `print`

Print the resolved variables for a given context.

**Syntax:**

```bash
envars2 print [OPTIONS]
```

**Examples:**

- Print all variables in a tree view:
  ```bash
  envars2 print
  ```
- Print variables for a specific context in `VAR=value` format:
  ```bash
  envars2 print --env dev --loc aws
  ```
- Decrypt and print secrets:
  ```bash
  envars2 print --env prod --loc aws --decrypt
  ```

**Output Examples:**

- Default tree view (`envars2 print`):
  ```
  Envars Configuration
  ├── App: my-app
  ├── KMS Key: arn:aws:kms:us-east-1:123456789012:key/mrk-12345
  ├── Environments
  │   ├── dev
  │   └── prod
  ├── Locations
  │   ├── aws (id: 123456789012)
  │   └── gcp (id: projects/my-gcp-project)
  └── Variables
      ├── API_KEY - API key for a third-party service.
      │   ├── (Scope: DEFAULT) Value: default-key
      │   ├── (Scope: ENVIRONMENT, Env: dev) Value: dev-key
      │   ├── (Scope: SPECIFIC, Env: prod, Loc: aws) Value: !secret encrypted-aws-key
      │   └── (Scope: SPECIFIC, Env: prod, Loc: gcp) Value: !secret encrypted-gcp-key
      ├── DB_HOST - Database host.
      │   ├── (Scope: DEFAULT) Value: localhost
      │   └── (Scope: ENVIRONMENT, Env: prod) Value: db.my-app.com
      └── DEBUG - Enable debug mode.
          ├── (Scope: DEFAULT) Value: false
          └── (Scope: ENVIRONMENT, Env: dev) Value: true
  ```
- `VAR=value` format (`envars2 print --env dev --loc aws`):
  ```
  API_KEY=dev-key
  DB_HOST=localhost
  DEBUG=true
  ```

### `exec`

Execute a command with the resolved environment variables.

**Syntax:**

```bash
envars2 exec --loc <location> [OPTIONS] -- <command>
```

**Example:**

```bash
envars2 exec --loc aws --env dev -- python my_script.py
```

### `yaml`

Output the resolved variables as a YAML object. Secrets are decrypted by default.

**Syntax:**

```bash
envars2 yaml --loc <location> [OPTIONS]
```

**Example:**

```bash
envars2 yaml --loc aws --env dev
```

**Output Example:**

```yaml
envars:
  API_KEY: dev-key
  DB_HOST: localhost
  DEBUG: true
```

### `set-systemd-env`

Set the environment variables for a systemd user service.

**Syntax:**

```bash
envars2 set-systemd-env --loc <location> [OPTIONS]
```

**Example:**

```bash
envars2 set-systemd-env --loc aws --env dev
```

### `validate`

Validate the `envars.yml` file for logical consistency.

**Syntax:**

```bash
envars2 validate
```

**Example:**

```bash
envars2 validate
```

### `rotate-kms-key`

Rotates the KMS key and re-encrypts all secrets to a new file.

**Syntax:**

```bash
envars2 rotate-kms-key --new-kms-key <new_key_arn_or_id> --output-file <new_file_path>
```

**Example:**

```bash
envars2 rotate-kms-key --new-kms-key "arn:aws:kms:us-east-1:123456789012:key/new-key" --output-file envars.new.yml
```

## Development

To set up the development environment, clone the repository and install the dependencies using `uv`:

```bash
git clone https://github.com/your-username/envars2.git
cd envars2
uv sync
```

To run the tests:

```bash
uv run pytest
```
