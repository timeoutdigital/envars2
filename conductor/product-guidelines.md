# Product Guidelines - Envars

## Tone and Style
- **Technical and Precise:** All documentation, error messages, and CLI outputs must prioritize accuracy and clarity. Use standard industry terminology (e.g., "KMS", "Environment Variables", "Jinja2 templating") to ensure professional and unambiguous communication with backend developers.

## Security Principles
- **Explicit and High-Visibility:** Security is a core pillar of Envars. Any operation involving secrets, encryption, or decryption MUST be clearly identified. Use high-visibility formatting in documentation and clear labels in CLI output to ensure users are aware when they are handling sensitive data.
- **Fail Securely:** If an encryption or decryption operation fails, the application must fail-fast with a clear, non-sensitive error message, ensuring no unencrypted secrets are accidentally exposed.

## User Experience (UX) Philosophy
- **Discoverability:** The CLI should be self-documenting. Use `typer` to provide comprehensive `--help` menus for all commands and subcommands.
- **Safety First:** Protect users from accidental data loss or exposure. Sensitive operations should provide clear feedback, and destructive actions should require confirmation or explicit flags.
- **Scriptability:** Envars is designed for automation. Ensure that output formats (like JSON) are consistent and easily parseable by other tools in a CI/CD pipeline.
- **Consistency:** Maintain a consistent command structure and naming convention across all features to reduce the learning curve for new users.
