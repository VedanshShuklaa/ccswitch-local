"""Security regressions: isolated fixtures, dummy credentials, no network."""
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'bin/ccswitch'
CREDS = {'claudeAiOauth': {'accessToken': 'DUMMY', 'refreshToken': 'DUMMY-R',
                         'expiresAt': 4102444800000, 'refreshTokenExpiresAt': 4102531200000}}


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ccswitch-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'config/vault'
        self.live = self.root / 'claude'
        self.live.mkdir()
        self.mock = self.root / 'bin'
        self.mock.mkdir()
        for cmd in ['curl', 'wget', 'npm', 'claude', 'pgrep']:
            p = self.mock / cmd
            p.write_text('#!/bin/sh\nprintf "%s\\n" "'+cmd+'" >> "$TEST_CALLS"\nexit 1\n')
            p.chmod(0o755)
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.live),
                        CCSWITCH_HOME=str(self.vault), CCSWITCH_BACKEND='file',
                        PATH=str(self.mock)+':/usr/bin:/bin',
                        TEST_CALLS=str(self.root/'calls'), NO_COLOR='1')
        self.env.pop('BASH_ENV', None)

    def run_cli(self, *args):
        return subprocess.run(['/bin/bash', str(SCRIPT), *map(str,args)],
                              env=self.env, capture_output=True, text=True,
                              umask=0o022, timeout=15)

    def archive(self, extras=(), identity=None):
        target = self.root / 'input.tgz'
        entries = [('vault', None), ('vault/accounts', None), ('vault/accounts/demo', None),
                   ('vault/accounts/demo/credentials.json', json.dumps(CREDS)),
                   ('vault/accounts/demo/identity.json', json.dumps(identity or {}))]
        with tarfile.open(target, 'w:gz') as tar:
            for name, content in entries + list(extras):
                info = tarfile.TarInfo(name)
                if content is None:
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o777
                    tar.addfile(info)
                elif isinstance(content, tuple):
                    info.type, info.linkname = content
                    tar.addfile(info)
                else:
                    data = content.encode()
                    info.mode = 0o666
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
        return target

    def test_restore_rejects_outside_members_before_writing(self):
        self.vault.mkdir(parents=True)
        marker = self.vault / 'keep'
        marker.write_text('KEEP')
        sibling = self.vault.parent / 'other'
        sibling.write_text('ORIGINAL')
        result = self.run_cli('restore', self.archive([('other','CHANGED')]))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sibling.read_text(), 'ORIGINAL')
        self.assertEqual(marker.read_text(), 'KEEP')
        self.assertFalse((self.vault/'accounts/demo').exists())

    def test_restore_rejects_links_traversal_duplicates_and_bad_json(self):
        for name, content in [('vault/accounts/demo/link', (tarfile.SYMTYPE, '/tmp')),
                              ('vault/accounts/demo/hard', (tarfile.LNKTYPE, 'vault/active')),
                              ('vault/../other', 'bad'), ('/tmp/ccswitch-forbidden', 'bad'),
                              ('vault/accounts/demo/identity.json', '{}'),
                              ('vault/mcp-oauth.json', 'not json')]:
            with self.subTest(name=name):
                result = self.run_cli('restore', self.archive([(name,content)]))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.vault/'accounts/demo').exists())

    def test_restore_normalizes_permissions_and_roundtrips(self):
        result = self.run_cli('restore', self.archive())
        self.assertEqual(result.returncode, 0, result.stderr)
        for p in [self.vault, *self.vault.rglob('*')]:
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o700 if p.is_dir() else 0o600)
        backup = self.root/'roundtrip.tgz'
        self.assertEqual(self.run_cli('backup', backup).returncode, 0)
        self.assertEqual(self.run_cli('restore', backup).returncode, 0)
        self.assertEqual(json.loads((self.vault/'accounts/demo/credentials.json').read_text()), CREDS)

    def test_identity_cannot_inject_config(self):
        self.assertEqual(self.run_cli('restore', self.archive(identity={
            'oauthAccount':{'emailAddress':'dummy@example.invalid'},
            'mcpServers':{'injected':{'command':'/bin/false'}}})).returncode, 0)
        (self.live/'.claude.json').write_text(json.dumps({'mcpServers':{'existing':{'url':'https://example.invalid'}}}))
        result = self.run_cli('use', 'demo', '--force')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(json.loads((self.live/'.claude.json').read_text())['mcpServers']), ['existing'])

    def test_backup_is_private_before_any_token_write(self):
        self.assertEqual(self.run_cli('restore', self.archive()).returncode, 0)
        # Instrument file opens in Python and tar's completed output, before
        # any post-write chmod. This catches the original tar creation bug.
        tar = self.mock/'tar'
        tar.write_text('#!/bin/sh\n/usr/bin/tar "$@" || exit $?\nif [ "$1" = czf ]; then /usr/bin/stat -c %a "$2" > "$TEST_MODE"; fi\n')
        tar.chmod(0o755)
        observer = self.root/'observer'
        observer.mkdir()
        (observer/'sitecustomize.py').write_text('''import os, stat, tarfile
original_add = tarfile.TarFile.add
def checked_add(self, *args, **kwargs):
    mode = stat.S_IMODE(os.fstat(self.fileobj.fileno()).st_mode)
    with open(os.environ["TEST_MODE"], "w") as result:
        result.write(format(mode, "o"))
    if mode != 0o600:
        raise ValueError("backup exposed before token write")
    return original_add(self, *args, **kwargs)
tarfile.TarFile.add = checked_add
''')
        self.env['PYTHONPATH'] = str(observer)
        self.env['TEST_MODE'] = str(self.root/'mode')
        backup = self.root/'backup.tgz'
        result = self.run_cli('backup', backup)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root/'mode').read_text().strip(), '600')
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)

    def test_update_aliases_never_contact_network(self):
        for args in [('update',), ('upgrade',), ('update','--check')]:
            result = self.run_cli(*args)
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/'calls').exists())

    def test_refresh_skip_never_checks_for_updates(self):
        self.assertEqual(self.run_cli('restore', self.archive()).returncode, 0)
        result = self.run_cli('refresh', '--all')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root/'calls').exists())

    def test_account_traversal_rejected(self):
        victim = self.vault.parent/'victim'
        victim.mkdir(parents=True)
        (victim/'keep').write_text('KEEP')
        result = self.run_cli('rm','../../victim')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((victim/'keep').exists())

    def test_restore_size_limit_leaves_existing_vault(self):
        self.vault.mkdir(parents=True)
        (self.vault/'keep').write_text('KEEP')
        archive = self.archive([('vault/mcp-oauth.json', ' ' * (16 * 1024 * 1024 + 1))])
        self.assertNotEqual(self.run_cli('restore', archive).returncode, 0)
        self.assertEqual((self.vault/'keep').read_text(), 'KEEP')

    def test_installer_is_local_only_and_independent_of_working_directory(self):
        prefix = self.root/'installed'
        env = dict(self.env, PREFIX=str(prefix))
        result = subprocess.run(['/bin/bash', str(ROOT/'install.sh')], cwd=self.root,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((prefix/'ccswitch').read_bytes(), SCRIPT.read_bytes())
        lone_installer = self.root/'install.sh'
        lone_installer.write_bytes((ROOT/'install.sh').read_bytes())
        result = subprocess.run(['/bin/bash', str(lone_installer)], cwd=self.root,
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/'calls').exists())

    def test_no_remote_installer_or_updater_code(self):
        for path in [SCRIPT, ROOT/'install.sh']:
            source = path.read_text()
            for forbidden in ['curl ', 'wget ', 'npm install', 'fetch_url', 'update_check',
                              'raw.githubusercontent.com', 'CCSWITCH_NPM_REGISTRY']:
                self.assertNotIn(forbidden, source)

    def test_symlink_account_destinations_rejected_before_writing(self):
        (self.vault/'accounts').mkdir(parents=True)
        outside = self.root/'outside'
        outside.mkdir()
        (self.vault/'accounts/demo').symlink_to(outside, target_is_directory=True)
        (self.live/'.credentials.json').write_text(json.dumps(CREDS))
        for args in [('add','demo'), ('login','demo')]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_cli(*args).returncode, 0)
                self.assertEqual(list(outside.iterdir()), [])
                self.assertTrue((self.live/'.credentials.json').exists())
        (self.vault/'accounts/source').mkdir()
        self.assertNotEqual(self.run_cli('rename','source','demo').returncode, 0)
        self.assertTrue((self.vault/'accounts/source').exists())

    def test_interrupted_restore_preserves_original_vault(self):
        self.check_restore_recovery('interrupt')

    def test_failed_rollback_preserves_recovery_copy(self):
        self.check_restore_recovery('rollback')

    def check_restore_recovery(self, failure):
        self.vault.mkdir(parents=True)
        (self.vault/'keep').write_text('KEEP')
        observer = self.root/'observer'
        observer.mkdir()
        (observer/'sitecustomize.py').write_text('''import os
original_rename = os.rename
def rename(src, dst, *args, **kwargs):
    if str(src).endswith('/new'):
        if os.environ['TEST_FAILURE'] == 'interrupt':
            raise KeyboardInterrupt()
        raise OSError('injected install failure')
    if os.environ['TEST_FAILURE'] == 'rollback' and str(dst) == os.environ['CCSWITCH_HOME']:
        raise OSError('injected rollback failure')
    return original_rename(src, dst, *args, **kwargs)
os.rename = rename
''')
        self.env.update(PYTHONPATH=str(observer), TEST_FAILURE=failure)
        result = self.run_cli('restore', self.archive())
        self.assertNotEqual(result.returncode, 0)
        copies = [p for p in self.vault.parent.rglob('keep') if p.read_text() == 'KEEP']
        self.assertTrue(copies, 'last original copy was deleted')
        if failure == 'interrupt':
            self.assertEqual((self.vault/'keep').read_text(), 'KEEP')
        else:
            self.assertIn('recovery', result.stderr.lower())


if __name__ == '__main__':
    unittest.main(verbosity=2)
