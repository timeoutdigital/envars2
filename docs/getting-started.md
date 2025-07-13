# Getting Started with Envars

This tutorial will guide you through the basics of using `envars` to manage your application's configuration. In about 5 minutes, you will go from installation to having a fully functional, version-controlled configuration file.

## 1. Installation

First, install `envars` using `pip`:

```bash
pip install envars
```

## 2. Initialize Your Project

The `envars init` command is the best way to start a new project. It creates the `envars.yml` file with the basic structure.

Let's create a configuration for an application named `MyApp` with `dev` and `prod` environments, running in two AWS accounts.

```bash
envars init \\
  --app MyApp \\
  --env "dev,prod" \\
  --loc "aws-dev:123456789012,aws-prod:987654321098" \\
  --kms-key "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
```

This will create an `envars.yml` file that looks like this:

```yaml
# envars.yml
configuration:
  app: MyApp
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
    - prod
  locations:
    - aws-dev: "123456789012"
    - aws-prod: "987654321098"

environment_variables: {}
```

## 3. Add Some Variables

Now, let's add some variables using the `envars add` command.

### A Simple Variable

Let's add a `LOG_LEVEL` that is `INFO` by default but `WARN` in production.

```bash
# Add the default value
envars add LOG_LEVEL=INFO --description "The application log level."

# Add the production-specific override
envars add LOG_LEVEL=WARN --env prod
```

### A Secret Variable

Secrets are automatically encrypted using the KMS key you provided. Let's add an `API_KEY`.

```bash
envars add API_KEY=super-secret-value --env prod --secret
```

The value will be encrypted and stored in the `envars.yml` file with a `!secret` tag.

### A Templated Variable

`envars` supports Jinja2 templating. This is great for creating dynamic values. Let's add a `DATABASE_URL` that changes based on the environment.

```bash
envars add DATABASE_URL="postgres://user:pass@db-{{ env.get('STAGE') }}.example.com/mydb"
```

## 4. View Your Configuration

The `envars tree` command provides a clear overview of your entire configuration, including all variables and their values across different scopes.

```bash
envars tree
```

This command helps you visualize the hierarchy and understand which value will be used in which context.

## 5. Export and Use Your Variables

The `envars output` command resolves the variables for a specific context and prints them in a format that can be sourced by your application.

To get the variables for the `dev` environment in the `aws-dev` location:

```bash
$ envars output --env dev --loc aws-dev
LOG_LEVEL=INFO
DATABASE_URL=postgres://user:pass@db-dev.example.com/mydb
```

To get the variables for `prod`, including the decrypted secret:

```bash
$ envars output --env prod --loc aws-prod
LOG_LEVEL=WARN
API_KEY=super-secret-value
DATABASE_URL=postgres://user:pass@db-prod.example.com/mydb
```

You can use this output to populate your shell's environment:

```bash
export $(envars output --env dev --loc aws-dev)
```

## 6. Execute a Command

Even better, use the `envars exec` command to run your application with the environment variables automatically loaded.

```bash
envars exec --env dev --loc aws-dev -- your_application --some-argument
```

This command injects the variables into the environment and then executes your application, keeping your configuration separate from your application's process.

---

You now have a solid, version-controlled foundation for managing your application's configuration. Explore the **User Guide** to learn about more advanced features.
