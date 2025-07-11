# Key Rotation in Envars2

This document discusses the process of key rotation and how it relates to the `envars2` application.

## Automated Key Rotation

`envars2` provides a `rotate-kms-key` command to simplify the process of rotating your KMS key. This command is designed to be safe, as it does not modify your existing `envars.yml` file. Instead, it creates a new file with all the secrets re-encrypted with the new key.

### Usage

1.  **Create a New KMS Key:** In your cloud provider's console (AWS KMS or GCP KMS), create a new KMS key.

2.  **Run the `rotate-kms-key` Command:**
    ```bash
    envars2 rotate-kms-key --new-kms-key "new-kms-key-arn-or-id" --output-file "envars.new.yml"
    ```
    This will:
    *   Decrypt all secrets in your existing `envars.yml` file using the old KMS key.
    *   Re-encrypt all secrets with the new KMS key.
    *   Create a new file named `envars.new.yml` with the re-encrypted secrets and the new KMS key in the configuration.

3.  **Verify and Replace:** Manually inspect the `envars.new.yml` file to ensure that the rotation was successful. Once you are confident, you can replace your old `envars.yml` file with the new one.

4.  **Decommission the Old Key:** After you have confirmed that the new key is working correctly, you can schedule the old key for deletion in your cloud provider's console.

## Manual Key Rotation

For users who prefer more granular control, a manual key rotation process is also possible.

1.  **Create a New KMS Key:** In your cloud provider's console (AWS KMS or GCP KMS), create a new KMS key.

2.  **Update Your `envars.yml`:** Change the `kms_key` in your `envars.yml` file to the new key's ARN or resource name. You can do this manually or by using the `envars2 config` command:
    ```bash
    envars2 config --kms-key "new-kms-key-arn-or-id"
    ```

3.  **Re-encrypt Your Secrets:** For each secret in your `envars.yml` file, you will need to re-encrypt it with the new key. You can do this by running the `add` command with the `--secret` flag for each secret.

    For example, if you have a secret named `MY_SECRET`, you would run:
    ```bash
    envars2 add MY_SECRET="the-secret-value" --secret --env <env> --loc <loc>
    ```
    This will re-encrypt the secret with the new key specified in your `envars.yml` file.

4.  **Commit and Deploy:** Once all your secrets have been re-encrypted, commit the changes to your `envars.yml` file and deploy your application.

5.  **Decommission the Old Key:** After you have confirmed that the new key is working correctly and all your secrets have been re-encrypted, you can schedule the old key for deletion in your cloud provider's console.
