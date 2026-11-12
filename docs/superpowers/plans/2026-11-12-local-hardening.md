# Local hardening implementation plan

Goal: fix the reproduced credential-handling problems and produce a local fork
with no updater, update checks, or remote installer. Existing account switching
continues to work. User authorization: fix the audit findings and create a fork;
subsequent instruction explicitly prohibits all updates.

Implementation: retain the single Bash executable with embedded Python standard
library helpers. No new runtime dependencies. Use an independent local clone so
the original checkout is preserved.

1. Add failing regression tests in test/security.py for hostile archive paths,
   links, restored permissions, identity injection, private backup creation,
   account path traversal, and disabled updates.
2. Harden bin/ccswitch: validate archive members before writing; extract regular
   files into private staging, normalize permissions, validate JSON, replace the
   vault only after validation; filter identity keys; create backups privately
   and publish atomically; validate every account argument.
3. Remove update/download code, remove registry publishing, make install.sh
   local-only, update README and existing tests to match the fork.
4. Run security, smoke, keychain and syntax checks with dummy credentials;
   independent review; fix material findings; commit and publish the fork to
   the user's GitHub account; install the reviewed local executable.

Review focus: failed restore leaves original intact; link and duplicate entries
are refused; archives cannot expand without bounds; no updater aliases or
installer fallback; no real credential access in tests.
