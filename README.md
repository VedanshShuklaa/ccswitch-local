# ccswitch-local

Personal, hardened fork of [2hmad/ccswitch](https://github.com/2hmad/ccswitch),
based on upstream commit `d303f8f9b276dc700c41e5dfc58dbde5f4e15248`.
Switch Claude Code accounts while sharing your existing configuration.

## No software updates

There is **no updater, update check, registry lookup, or remote installer**.
`ccswitch update`, `upgrade`, and `update --check` fail without network access.
Environment variables cannot re-enable updates. This repository does not publish
npm packages or automated releases. To change the tool, edit this local source,
review and test it, then explicitly run `bash install.sh` again.

`refresh` still renews account login tokens through your installed Claude Code;
it does not download or update ccswitch. Claude Code itself may access the network
and run its configured integrations. This fork does not control Claude's own updates.

## Local installation

Requires Bash, Python 3, and an existing Claude Code installation.

```bash
cd ~/projects/ccswitch-local
bash install.sh
ccswitch version
```

Installs the reviewed local `bin/ccswitch` to `~/.local/bin/ccswitch`.
The installer resolves its own source directory and never downloads a replacement.
If needed, add `~/.local/bin` to your shell PATH.

## Use

```bash
ccswitch add personal       # save the account already logged in
ccswitch login work         # open Claude; /login, then /exit
ccswitch list
ccswitch personal
claude
```

Exit active Claude sessions before switching. Accounts share settings, MCP
servers, plugins, history and project permissions; this is not account isolation.
`ccswitch help` lists all supported commands. No login or token migration occurs
merely by installing this fork.

## Security changes

- Private creation mask (`077`), private temporary backups, atomic backup publication.
- Restores accept only known vault files and directories; reject links, special
  files, duplicate paths, path traversal and malformed JSON before replacing data.
- Restores stage privately and normalize directories to `700`, files to `600`.
  Archive limits: 64 MiB expanded tar, 32 MiB file contents, 16 MiB per file,
  4096 members. Legacy update cache is discarded.
- Only `oauthAccount` and `userID` are applied from identity files. Restores cannot
  inject MCP configuration through extra identity keys.
- Account arguments reject traversal and symlinked account directories.
- All software-update and remote-install code has been removed.

## Backups

```bash
ccswitch backup /secure/location/accounts.tar.gz
ccswitch restore /secure/location/accounts.tar.gz
```

Backups contain **unencrypted live Claude and MCP tokens**. Keep them private.
Restore replaces the vault; use only your own trusted backups. It does not change
which credentials Claude is currently using until you switch accounts. Stop
concurrent ccswitch commands/autosync before restoring. The archive root must match
your vault directory name (normally `ccswitch`).
If a failed restore cannot roll back, it prints the private recovery directory
containing the original vault. Keep that directory until you recover your accounts.

The vault is normally `~/.config/ccswitch`. `CCSWITCH_HOME` overrides it;
`CLAUDE_CONFIG_DIR` controls the live Claude directory. macOS uses the Keychain
for the live credential, but the account vault and backups are still plaintext.
Processes running as your OS user can read your tokens; this tool is not a sandbox.

## Verification

```bash
python3 test/security.py
bash test/smoke.sh
bash test/keychain.sh
bash -n bin/ccswitch
bash -n install.sh
```

On Linux, run the shell suites with `PATH=/usr/bin:/bin` to exclude an installed
Claude executable and avoid interference from real running Claude sessions.

Tests use temporary paths and dummy credentials. The keychain suite uses a mock;
it does not establish real macOS Keychain compatibility.

MIT licensed; original copyright retained in LICENSE. Upstream history is retained
in CHANGELOG.md; its old update/install instructions do not apply to this fork.
