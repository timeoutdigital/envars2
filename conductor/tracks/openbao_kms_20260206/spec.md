# Specification: Add Openbao as a KMS provider

## 1. Overview
Add support for Openbao (a fork of HashiCorp Vault) as a Key Management Service (KMS) provider in Envars. This will allow users to encrypt and decrypt sensitive configuration values using Openbao's Transit Secrets Engine.

## 2. Goals
- enable usage of Openbao for encryption/decryption operations.
- Maintain consistency with existing AWS and GCP KMS implementations.
- Provide a secure and auditable alternative for on-premise or cloud-agnostic secret management.

## 3. User Stories
- As a backend developer, I want to configure Envars to use my Openbao instance so that I can encrypt secrets without relying on AWS or GCP.
- As a security engineer, I want to use Openbao's Transit engine to manage encryption keys centrally.

## 4. Functional Requirements
- **Configuration:**
    - Support defining Openbao configuration in `envars.yml` under a new `openbao` key or within the `kms` section.
    - Required parameters: `address` (URL), `token` (auth), and `transit_mount` (optional, default to 'transit').
    - Support reading the Openbao token from environment variables (e.g., `VAULT_TOKEN`) for security.
- **Encryption:**
    - Implement a new KMS provider class `OpenBaoKMS`.
    - Support the `encrypt` method using the Transit engine's `encrypt` endpoint.
- **Decryption:**
    - Support the `decrypt` method using the Transit engine's `decrypt` endpoint.
- **CLI Integration:**
    - Update `envars init` to optionally scaffold Openbao configuration.
    - Ensure `envars add --secret` works seamlessly with Openbao when configured as the active KMS.

## 5. Non-Functional Requirements
- **Security:** Ensure the Openbao token is never logged or exposed in plain text.
- **Performance:** Minimise latency when making API calls to the Openbao instance.
- **Error Handling:** Provide clear error messages if the Openbao instance is unreachable or if authentication fails.

## 6. API/Interface Changes
- **`envars.yml` Structure:**
    ```yaml
    configuration:
      kms:
        provider: openbao
        key: "my-encryption-key-name"
        address: "https://openbao.example.com"
        transit_mount: "transit"
    ```
