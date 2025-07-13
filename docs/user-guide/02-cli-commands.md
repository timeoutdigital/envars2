# User Guide: CLI Commands

The `envars` command-line interface (CLI) is the primary way to interact with your `envars.yml` file. This guide covers the most important commands and their options.

All commands can be run with the `--help` flag to see a full list of options (e.g., `envars add --help`).

---

## `envars init`

Initializes a new `envars.yml` file in the current directory.

*   **Usage:** `envars init [OPTIONS]`

### Key Options

*   `--app <name>`: (Required) The name of your application.
*   `--env <list>`: (Required) A comma-separated list of environments (e.g., `"dev,prod"`).
*   `--loc <list>`: (Required) A comma-separated list of locations in `name:id` format (e.g., `"aws-dev:12345,gcp-prod:my-proj"`).
*   `--kms-key <key>`: The ARN or resource name of the default KMS key for secrets.
*   `--force`: Overwrite an existing `envars.yml` file.

---

## `envars add`

Adds or updates a variable in the `envars.yml` file.

*   **Usage:** `envars add <VAR=value> [OPTIONS]`

### Key Options

*   `<VAR=value>`: The variable assignment.
*   `--description <text>`: A description for the variable.
*   `--env <name>`: Scope the variable to a specific environment.
*   `--loc <name>`: Scope the variable to a specific location.
*   `--secret`: Encrypt the value using the configured KMS key. The variable must be scoped to at least an environment or location.
*   `--validation <regex>`: A regex pattern to validate the value against.

---

## `envars output`

Resolves and prints the variables for a given context. This is the primary way to get variables into your application's environment.

*   **Usage:** `envars output [OPTIONS]`

### Key Options

*   `--env <name>`: (Required) The environment to resolve variables for.
*   `--loc <name>`: The location to resolve variables for. If not provided, `envars` will attempt to detect the default location based on your cloud credentials.
*   `--format <format>`: The output format. Can be `dotenv` (default), `json`, or `yaml`.

### Example

```bash
# Export variables for the 'dev' environment in 'aws-dev'
export $(envars output --env dev --loc aws-dev)
```

---

## `envars exec`

Executes a command with the environment variables from a specified context automatically loaded.

*   **Usage:** `envars exec [OPTIONS] -- <COMMAND>`

### Key Options

*   `--env <name>`: (Required) The environment to resolve variables for.
*   `--loc <name>`: The location to resolve variables for.

### Example

```bash
# Run a Python script with the 'prod' environment variables
envars exec --env prod --loc aws-prod -- python my_app.py --listen 0.0.0.0
```

---

## `envars tree`

Displays a tree view of the entire configuration, showing all variables, environments, locations, and their values. This is useful for visualizing the inheritance hierarchy.

*   **Usage:** `envars tree [OPTIONS]`

### Key Options

*   `--decrypt`: Show the decrypted values of secrets.

---

## `envars validate`

Checks the `envars.yml` file for logical consistency, such as circular dependencies, missing descriptions, or invalid values.

*   **Usage:** `envars validate`

---

## `envars config`

Updates the global `configuration` section of the `envars.yml` file.

*   **Usage:** `envars config [OPTIONS]`

### Key Options

*   `--kms-key <key>`: Update the default KMS key.
*   `--add-env <name>`: Add a new environment.
*   `--remove-env <name>`: Remove an environment.
*   `--add-loc <name:id>`: Add a new location.
*   `--remove-loc <name>`: Remove a location.
