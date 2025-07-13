# API Reference: Using Envars as a Library

While `envars` is primarily a command-line tool, it is built as a Python library and can be used directly in your Python applications. This is useful if you need to integrate its configuration management capabilities more deeply into your code.

## Core Functions

The two most important functions for library usage are `get_env` and `get_all_envs` from the `envars.main` module.

### `get_env(env, loc, file_path)`

This function loads, resolves, and decrypts all variables for a **single, specific context**.

*   **Arguments:**
    *   `env` (str): The name of the environment (e.g., `"prod"`).
    *   `loc` (str): The name of the location (e.g., `"aws-prod"`).
    *   `file_path` (str, optional): The path to your `envars.yml` file. Defaults to `"envars.yml"`.

*   **Returns:**
    *   A dictionary of the resolved environment variables.

*   **Example:**

    ```python
    from envars.main import get_env

    try:
        # Get the configuration for the 'prod' env in 'aws-prod'
        prod_config = get_env(env="prod", loc="aws-prod")

        # Now you can use it like a dictionary
        api_key = prod_config.get("API_KEY")
        log_level = prod_config.get("LOG_LEVEL")

        print(f"API Key: {api_key}")
        print(f"Log Level: {log_level}")

    except ValueError as e:
        print(f"Error loading configuration: {e}")
    ```

### `get_all_envs(loc, file_path)`

This function loads and resolves variables for **all defined environments** within a single location.

*   **Arguments:**
    *   `loc` (str): The name of the location (e.g., `"aws-prod"`).
    *   `file_path` (str, optional): The path to your `envars.yml` file. Defaults to `"envars.yml"`.

*   **Returns:**
    *   A dictionary where keys are environment names and values are dictionaries of the resolved variables for that environment.

*   **Example:**

    ```python
    from envars.main import get_all_envs

    try:
        # Get the configuration for all envs in the 'aws-prod' location
        all_configs = get_all_envs(loc="aws-prod")

        dev_config = all_configs.get("dev")
        prod_config = all_configs.get("prod")

        print("--- Dev Config ---")
        print(dev_config)

        print("\\n--- Prod Config ---")
        print(prod_config)

    except ValueError as e:
        print(f"Error loading configuration: {e}")
    ```

## Automatic Location Detection

If you pass `loc=None` (or omit it) to either `get_env` or `get_all_envs`, `envars` will attempt to automatically detect the location by checking your machine's current cloud credentials (either the AWS account ID or the GCP project ID).
