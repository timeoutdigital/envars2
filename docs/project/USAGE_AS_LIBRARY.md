# Using Envars2 as a Library

Envars2 can be used as a library to load and manage environment variables in your Python applications.

The primary function for library usage is `envars.get_env`. This function loads an `envars.yml` file, resolves the variables for a specific environment and location, and returns them as a dictionary.

### `get_env(env, loc, file_path="envars.yml")`

-   `env` (str): The environment to load (e.g., "dev", "prod").
-   `loc` (str): The location to load (e.g., "aws", "gcp").
-   `file_path` (str, optional): The path to the `envars.yml` file. Defaults to "envars.yml".

**Returns:** A dictionary of the resolved environment variables.

**Example:**

```python
import os
from envars.main import get_env

# Load variables for the 'dev' environment and 'aws' location
try:
    env_vars = get_env(env="dev", loc="aws")

    # Use the variables
    os.environ.update(env_vars)

    print(os.environ.get("MY_VARIABLE"))

except (ValueError, FileNotFoundError) as e:
    print(f"Error: {e}")
```
