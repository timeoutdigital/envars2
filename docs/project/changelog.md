# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - YYYY-MM-DD

### Added

*   Initial release of `envars`.
*   Core functionality for managing environment variables via `envars.yml`.
*   Support for environments, locations, and hierarchical value resolution.
*   Encryption and decryption of secrets with AWS KMS and GCP KMS.
*   Dynamic variable resolution from AWS Parameter Store, AWS CloudFormation Exports, and GCP Secret Manager.
*   Jinja2 templating for variable values.
*   CLI commands: `init`, `add`, `output`, `exec`, `tree`, `validate`, `config`, and `rotate-kms-key`.
