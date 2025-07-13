# Envars2 Security

This document provides a security assessment of the `envars2` application, outlining its security strengths, potential risks, and best practices for secure usage.

## Security Strengths

1.  **Explicit Encryption by Default:** The application never encrypts data unless the user explicitly provides the `--secret` flag. This "opt-in" model for a sensitive action is a core security principle that prevents accidental encryption and ensures user intent is clear.

2.  **Context-Aware Encryption:** This is a major strength. By including the application name, environment, and location in the [encryption context](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#encrypt_context), `envars2` allows for highly granular access control. You can create IAM policies that only allow a specific role in a specific environment (e.g., the `prod` server role) to decrypt secrets tagged for that context. This significantly reduces the risk of a secret from one environment being decrypted and used in another.

3.  **Proactive Secret Detection:** The application doesn't just wait for the user to specify `--secret`. It actively looks for keywords like `PASSWORD`, `TOKEN`, `SECRET`, and `KEY` in variable names. If it finds one, it forces the user to make an explicit choice: either encrypt it with `--secret` or confirm it should be plaintext with `--no-secret`. This is a powerful guardrail against accidental unencrypted commits of sensitive data.

4.  **Prevention of Default Secrets:** The application enforces a rule that prevents secrets from being defined with a `default` scope. This is a critical security measure that mitigates the risk of a production secret accidentally being inherited by a development or staging environment.

5.  **Cloud Provider Validation:** The tool checks that the remote variable prefixes (e.g., `parameter_store:`) match the cloud provider indicated by the KMS key. This prevents misconfigurations where a user might try to access a GCP secret while configured with an AWS KMS key, reducing confusion and potential errors.

## Potential Risks and Weaknesses

1.  **The `envars.yml` File as a Single Point of Failure:**
    *   **Risk:** The biggest risk is a developer accidentally committing an unencrypted secret to the repository. While the keyword detection helps, it's not foolproof (e.g., a variable named `API_CREDENTIAL`).
    *   **Mitigation:** This risk should be mitigated with `pre-commit` hooks that scan for secrets. Tools like `trufflehog` or `git-secrets` can be integrated into the development workflow to prevent such accidents.

2.  **Jinja2 Templating Power:**
    *   **Risk:** The `jinja2` templating engine is powerful, but that power can be misused. We are passing the shell's environment variables into the template context via `env=os.environ`. A malicious or poorly crafted template could access sensitive information from the user's shell environment. For example, a template with `{{ env.get('AWS_SECRET_ACCESS_KEY') }}` would expose the user's secret key if it's set in their environment.
    *   **Mitigation:** The best practice here would be to use `jinja2.sandbox.SandboxedEnvironment`. This would create a restricted execution environment for the templates, preventing them from accessing potentially dangerous attributes or functions, including `os.environ`.

3.  **The `exec` Command's Inherent Power:**
    *   **Risk:** The `exec` command is designed to execute arbitrary commands with the resolved environment. If a user is tricked into running `envars2 exec` on a malicious `envars.yml` file from an untrusted source, it could lead to arbitrary code execution.
    *   **Mitigation:** This is an inherent risk in any tool that provides this kind of functionality. The primary mitigation is user education and documentation, which should clearly warn users to only run the `exec` command on trusted configuration files.

4.  **Overly Permissive IAM Roles:**
    *   **Risk:** The security of the encrypted secrets is only as strong as the IAM policies that protect the KMS key. If a user grants overly broad permissions (e.g., `kms:Decrypt` on `*` for all principals), the benefit of the encryption context is lost.
    *   **Mitigation:** The documentation should include a section on security best practices, advising users to follow the principle of least privilege when creating IAM policies for the KMS key.

## Conclusion

`envars2` has a strong security foundation. Its design encourages secure practices by making encryption explicit, preventing common mistakes like default secrets, and providing proactive warnings.

The most significant potential risks are not in the tool itself, but in how it's used and configured:

*   **Users must be careful not to commit unencrypted secrets.**
*   **The Jinja2 environment could be made more secure by using a sandbox.**
*   **Users must be educated about the power of the `exec` command.**
*   **Proper IAM policies are critical to the overall security model.**

Overall, it is a well-designed tool that, when used correctly and supplemented with standard security practices like pre-commit hooks, provides a secure and effective way to manage environment variables and secrets.
