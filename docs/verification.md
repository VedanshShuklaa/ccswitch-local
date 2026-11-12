# Local fork verification

Base: upstream d303f8f9b276dc700c41e5dfc58dbde5f4e15248.

Final checks on 2026-11-12:

- Security: 14 tests passed, including hostile archive members, restore limits,
  private backup writes, identity filtering, account traversal/symlinks, update
  denial, local installation, interrupted restore, and failed rollback recovery.
- Existing smoke suite: 85 passed, zero failures. Tests for deleted version
  comparison/update installation were removed or replaced with update rejection.
- Mock Keychain suite: 22 passed, zero failures.
- Bash syntax and git diff whitespace checks passed.

All credential tests used temporary fixtures. No real accounts were logged in,
switched, or copied as part of verification. Shell suites ran with a clean system
PATH to exclude the user's live Claude installation.

An independent reviewer found interrupted-restore data loss and symlink account
destinations during development. Both were reproduced with failing regressions,
fixed, and verified in the final full run. The previous vault is now preserved
outside automatically cleaned staging until restore commits successfully.

Scope: this is a targeted hardening review, not a guarantee against all defects.
Real macOS Keychain integration was not exercised. Vault/backup tokens remain
plaintext and accessible to the owning OS user. Existing shared Claude settings,
integrations, and Claude's own update behavior remain under the user's control.
