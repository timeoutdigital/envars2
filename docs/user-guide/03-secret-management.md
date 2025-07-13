# User Guide: Secret Management

`envars` provides a secure and straightforward way to manage secrets, such as API keys, database passwords, and tokens, by integrating with **AWS Key Management Service (KMS)** and **Google Cloud KMS**.

## How it Works

When you add a variable with the `--secret` flag, `envars` performs the following steps:

1.  It uses the KMS key defined in your `envars.yml` file (`configuration.kms_key`) to encrypt the value you provide.
2.  The encrypted value (ciphertext) is stored in the `envars.yml` file with the `!secret` YAML tag.
3.  The original plaintext value is never stored on disk.

When you need the secret (using `envars output` or `envars exec`), `envars` automatically decrypts the value in memory using the same KMS key.

## Adding a Secret

To add a secret, use the `envars add` command with the `--secret` flag.

**Important:** Secrets **must** be scoped to at least an environment or a location. They cannot be set as default values, as this would create an insecure fallback.

```bash
# Add a secret for the 'prod' environment
envars add STRIPE_API_KEY=sk_prod_... --env prod --secret

# Add a secret for a specific location
envars add DYNATRACE_TOKEN=dt_... --loc gcp-prod --secret

# Add a secret for a specific environment AND location
envars add RABBITMQ_PASSWORD=... --env staging --loc aws-staging --secret
```

Your `envars.yml` file will store the encrypted value:

```yaml
environment_variables:
  STRIPE_API_KEY:
    description: "The Stripe API key."
    prod: !secret "CiD...some-long-encrypted-blob...=="
```

## Decrypting and Using Secrets

Secrets are automatically decrypted when you use `envars output` or `envars exec`. You don't need to do anything special.

```bash
# The value of STRIPE_API_KEY will be the decrypted plaintext
export $(envars output --env prod --loc aws-prod)

# Your application will receive the decrypted secret in its environment
envars exec --env prod --loc aws-prod -- ./my-app
```

## Viewing Secrets

The `envars tree` command will, by default, show a truncated version of the encrypted secret for security.

To view the *decrypted* value in the tree, use the `--decrypt` flag:

```bash
envars tree --decrypt
```

## Key Rotation

If you need to change your KMS key, `envars` provides a safe way to do so with the `rotate-kms-key` command. This command will:

1.  Decrypt all secrets using the old key.
2.  Re-encrypt them with the new key.
3.  Save the result to a new configuration file, leaving your original file untouched.

```bash
envars rotate-kms-key \\
  --new-kms-key "arn:aws:kms:us-east-1:123456789012:key/new-key-id" \\
  --output-file "envars.new.yml"
```

After verifying the new file, you can replace your old `envars.yml` with it.
