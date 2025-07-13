# User Guide: Value Validation

To ensure the integrity and consistency of your configuration, `envars` allows you to define validation rules for your variables. This helps prevent common errors, such as an invalid email address or a database URL that doesn't conform to the expected format.

## How it Works

Validation is performed using **regular expressions (regex)**. You can add a `validation` key to any variable definition in your `envars.yml` file.

`envars` checks the validation rule at two different times:

1.  **On `envars add`:** When you add or update a variable, `envars` checks the new value against the regex. If it doesn't match, the operation is aborted.
2.  **On `envars validate`:** The `validate` command will check *all* defined values for a variable against its rule, ensuring that even older values are still valid.

## Defining a Validation Rule

You can add a validation rule when you first create a variable using the `--validation` flag with `envars add`.

```bash
envars add ADMIN_EMAIL="admin@example.com" \\
  --description "The primary admin email." \\
  --validation "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
```

This will create the following entry in your `envars.yml`:

```yaml
# In envars.yml
environment_variables:
  ADMIN_EMAIL:
    description: "The primary admin email."
    validation: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    default: "admin@example.com"
```

## How Validation is Enforced

Once a validation rule is in place, `envars` will enforce it.

### Example

If you try to add an invalid email address to the `ADMIN_EMAIL` variable:

```bash
$ envars add ADMIN_EMAIL="not-an-email" --env prod
```

`envars` will reject the change and exit with an error:

```
Error: Value 'not-an-email' for variable 'ADMIN_EMAIL' does not match validation regex: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
```

## Validating Your Entire Configuration

To check all the values in your `envars.yml` file against their respective validation rules, simply run:

```bash
envars validate
```

If any value, whether it's a default, environment-specific, or location-specific value, does not match its variable's validation rule, the command will fail and report the error. This is a great way to ensure your entire configuration is healthy, and it's a recommended step to include in your CI/CD pipeline.
