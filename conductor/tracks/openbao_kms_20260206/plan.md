# Implementation Plan - Add Openbao as a KMS provider

## Phase 1: Setup and Configuration
- [ ] Task: Create a reproduction test case that fails because Openbao is not yet supported.
    - [ ] Create a test in `tests/test_openbao_kms.py` that attempts to initialize and use an Openbao KMS provider.
- [ ] Task: Update `envars.yml` schema and model definitions to support Openbao configuration.
    - [ ] Modify `src/envars/models.py` to include `OpenBaoConfig`.
    - [ ] Update validation logic to ensure required fields (address, key) are present.
- [ ] Task: Conductor - User Manual Verification 'Setup and Configuration' (Protocol in workflow.md)

## Phase 2: Core Implementation
- [ ] Task: Implement the `OpenBaoKMS` class.
    - [ ] Create `src/envars/openbao_kms.py`.
    - [ ] Implement authentication (Token-based initially).
    - [ ] Implement `encrypt` method using `hvac` or direct HTTP requests.
    - [ ] Implement `decrypt` method.
- [ ] Task: Integrate `OpenBaoKMS` into the main KMS factory.
    - [ ] Update `src/envars/kms_factory.py` (or equivalent) to instantiate `OpenBaoKMS` when the provider is 'openbao'.
- [ ] Task: Conductor - User Manual Verification 'Core Implementation' (Protocol in workflow.md)

## Phase 3: CLI and Testing
- [ ] Task: Update CLI commands to support Openbao.
    - [ ] Verify `envars add --secret` works with Openbao.
    - [ ] Verify `envars exec` correctly decrypts values.
- [ ] Task: Add comprehensive unit and integration tests.
    - [ ] Mock Openbao API responses in `tests/test_openbao_kms.py`.
    - [ ] Add integration tests (skipped by default unless an Openbao instance is available).
- [ ] Task: Update documentation.
    - [ ] Add a new section to `README.md` or `docs/` explaining how to configure and use Openbao.
- [ ] Task: Conductor - User Manual Verification 'CLI and Testing' (Protocol in workflow.md)
