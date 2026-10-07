#!/usr/bin/env python3
"""Read Skills Manager presets and launch agents with additive session skills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

SM = Path.home() / '.skills-manager/bin/skills-manager-cli'
ROOT = Path(__file__).resolve().parent / 'bundles'


class Error(Exception):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    skills: tuple[Skill, ...]


def resolve_cli(cli):
    path = Path(cli).expanduser()
    if path == SM:
        stamp = path.parent / '.version'
        if not stamp.is_file() or not stamp.read_text().strip() or not os.access(path, os.X_OK):
            raise Error('Skills Manager CLI bridge is incomplete. Open Skills Manager to republish it.')
    if not path.is_file() or not os.access(path, os.X_OK):
        raise Error(f'Skills Manager CLI is not executable: {path}')
    return path


def read_cli(cli, *args):
    cli = resolve_cli(cli)
    result = subprocess.run([str(cli), '--json', *args], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise Error(f'Skills Manager failed: {result.stderr.strip() or result.stdout.strip()}')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise Error('Skills Manager returned invalid JSON') from exc


def load_preset(cli, selector):
    presets = read_cli(cli, 'presets', 'list')
    if not isinstance(presets, list):
        raise Error('Unexpected preset list format')
    if any(not isinstance(p, dict) or not isinstance(p.get('id'), str) or not p['id']
           or not isinstance(p.get('name'), str) for p in presets):
        raise Error('Unexpected preset record format')
    matches = [p for p in presets if p.get('id') == selector or p.get('name') == selector]
    if len(matches) != 1:
        raise Error(f'Preset must match exactly one name or ID: {selector!r}')
    p = matches[0]
    records = read_cli(cli, 'skills', 'list', '--preset', p['id'])
    if not isinstance(records, list):
        raise Error('Unexpected skill list format')
    skills = []
    names = set()
    for record in records:
        if not isinstance(record, dict):
            raise Error('Unexpected skill record format')
        name = record.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name) or name in {'.', '..'}:
            raise Error(f'Unsafe skill folder name: {name!r}')
        if name.casefold() in names:
            raise Error(f'Duplicate skill folder name: {name}')
        names.add(name.casefold())
        raw_path = record.get('path')
        if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
            raise Error(f'Skill path must be absolute: {name}')
        path = Path(raw_path).resolve(strict=True)
        if not path.is_dir() or not (path / 'SKILL.md').is_file():
            raise Error(f'Skill is missing SKILL.md: {path}')
        skills.append(Skill(name, path))
    return Preset(str(p['id']), str(p['name']), tuple(sorted(skills, key=lambda s: s.name)))


def bundle(preset, root):
    root = Path(root).absolute()
    forbidden = [Path('/Applications/skills-manager.app'), Path.home() / '.skills-manager',
                 Path.home() / '.claude', Path.home() / '.codex', Path.home() / '.agents']
    resolved = root.resolve()
    if any(resolved == p or resolved.is_relative_to(p) for p in forbidden):
        raise Error('Bundle root must be outside official and global agent directories')
    if root.is_symlink():
        raise Error('Bundle root must not be a symlink')
    marker = root / '.sm-plugin-owned'
    root.parent.mkdir(parents=True, exist_ok=True)
    if not root.exists():
        claim = Path(tempfile.mkdtemp(prefix='.sm-root-', dir=root.parent))
        try:
            (claim / marker.name).write_text('sm-plugin 1\n')
            try:
                claim.rename(root)
            except OSError:
                if not root.exists():
                    raise
        finally:
            if claim.exists():
                shutil.rmtree(claim)
    if marker.is_symlink() or not marker.is_file() or marker.read_text() not in {'', 'sm-plugin 1\n'}:
        raise Error(f'Refusing unmanaged bundle root: {root}')
    profile = 'sm-' + hashlib.sha256(preset.id.encode()).hexdigest()[:16]
    manifest = {'format': 1, 'preset_id': preset.id, 'preset_name': preset.name,
                'mode': 'additive', 'skills': [{'name': s.name, 'path': str(s.path)} for s in preset.skills]}
    data = json.dumps(manifest, sort_keys=True, indent=2) + '\n'
    digest = hashlib.sha256(data.encode()).hexdigest()[:24]
    destination = root / f'{profile}-{digest}'
    if destination.exists() or destination.is_symlink():
        verify_bundle(destination, data, preset, profile)
        return destination
    stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=root))
    try:
        (stage / 'skills').mkdir()
        for skill in preset.skills:
            (stage / 'skills' / skill.name).symlink_to(skill.path, target_is_directory=True)
        (stage / '.claude-plugin').mkdir()
        (stage / '.claude-plugin/plugin.json').write_text(json.dumps({'name': profile, 'version': '1.0.0',
             'description': f'Skills Manager preset {preset.name}'}, indent=2) + '\n')
        (stage / 'manifest.json').write_text(data)
        try:
            stage.rename(destination)
        except OSError:
            if not destination.exists():
                raise
            verify_bundle(destination, data, preset, profile)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def verify_bundle(path, data, preset, profile):
    if path.is_symlink() or not path.is_dir():
        raise Error(f'Refusing unmanaged bundle: {path}')
    expected = {'skills', '.claude-plugin', 'manifest.json'}
    if {p.name for p in path.iterdir()} != expected or (path / 'manifest.json').is_symlink():
        raise Error(f'Bundle was changed outside the companion: {path}')
    if (path / 'manifest.json').read_text() != data:
        raise Error(f'Bundle manifest differs: {path}')
    skills_dir = path / 'skills'
    plugin_dir = path / '.claude-plugin'
    if skills_dir.is_symlink() or plugin_dir.is_symlink():
        raise Error(f'Bundle directories must not be symlinks: {path}')
    if {p.name for p in skills_dir.iterdir()} != {s.name for s in preset.skills}:
        raise Error(f'Bundle skill folders differ: {path}')
    for s in preset.skills:
        link = skills_dir / s.name
        if not link.is_symlink() or os.readlink(link) != str(s.path):
            raise Error(f'Bundle skill link differs: {link}')
    if {p.name for p in plugin_dir.iterdir()} != {'plugin.json'}:
        raise Error(f'Bundle plugin files differ: {path}')
    plugin = plugin_dir / 'plugin.json'
    if plugin.is_symlink() or json.loads(plugin.read_text()).get('name') != profile:
        raise Error(f'Bundle plugin identity differs: {path}')


def rpc(client, request_id, method, params):
    client.send(json.dumps({'id': request_id, 'method': method, 'params': params}))
    while True:
        response = json.loads(client.recv(timeout=15))
        if response.get('id') == request_id:
            if 'error' in response:
                raise Error(f'Codex {method} failed: {response["error"]}')
            return response['result']


def codex_session(executable, directory, cwd, args, smoke=False):
    try:
        from websockets.sync.client import unix_connect
    except ImportError as exc:
        raise Error('Install sm-plugin and its dependencies with pip install -e . from the project directory') from exc
    with tempfile.TemporaryDirectory(prefix='sm-codex-') as temporary:
        runtime = Path(temporary)
        socket = runtime / 's.sock'
        endpoint = 'unix://' + str(socket)
        with (runtime / 'server.log').open('w+') as log:
            server = subprocess.Popen([executable, 'app-server', '--listen', endpoint], cwd=cwd,
                                      stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 15
                while not socket.exists():
                    if server.poll() is not None:
                        log.seek(0)
                        raise Error('Codex app-server exited: ' + log.read()[-4000:])
                    if time.monotonic() > deadline:
                        raise Error('Codex app-server socket startup timed out')
                    time.sleep(.05)
                with unix_connect(str(socket), uri='ws://localhost', open_timeout=10) as client:
                    rpc(client, 1, 'initialize', {'clientInfo': {'name': 'sm_plugin', 'version': '0.1.0'},
                         'capabilities': {'experimentalApi': True}})
                    client.send(json.dumps({'method': 'initialized'}))
                    rpc(client, 2, 'skills/extraRoots/set', {'extraRoots': [str(directory / 'skills')]})
                if smoke:
                    with unix_connect(str(socket), uri='ws://localhost', open_timeout=10) as client:
                        rpc(client, 1, 'initialize', {'clientInfo': {'name': 'sm_plugin_verify', 'version': '0.1.0'},
                             'capabilities': {'experimentalApi': True}})
                        client.send(json.dumps({'method': 'initialized'}))
                        result = rpc(client, 2, 'skills/list', {'cwds': [str(cwd)], 'forceReload': True})
                    manifest = json.loads((directory / 'manifest.json').read_text())
                    found = {str(Path(s['path']).resolve()) for d in result['data'] for s in d['skills'] if s.get('enabled', True)}
                    missing = [s['name'] for s in manifest['skills'] if str((Path(s['path']) / 'SKILL.md').resolve()) not in found]
                    if missing:
                        raise Error('Codex did not discover enabled preset skills: ' + ', '.join(missing))
                    print(json.dumps({'agent': 'codex', 'preset_skills_verified': len(manifest['skills']),
                                      'mode': 'additive', 'model_turns': 0}))
                    return 0
                return subprocess.call([executable, '--remote', endpoint, '--cd', str(cwd), *args], cwd=cwd)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def doctor(cli):
    cli = resolve_cli(cli)
    result = {'skills_manager': str(cli), 'preset_count': len(read_cli(cli, 'presets', 'list')),
              'mode': 'additive', 'exclusive_supported': False, 'agents': {}}
    for agent, required in [('claude', '--plugin-dir'), ('codex', '--remote')]:
        executable = shutil.which(agent)
        if not executable:
            result['agents'][agent] = {'available': False}
            continue
        help_result = subprocess.run([executable, '--help'], capture_output=True, text=True, timeout=15)
        version = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=15)
        result['agents'][agent] = {'available': True, 'version': version.stdout.strip(),
                                   'launch_flag_supported': required in help_result.stdout}
    try:
        import websockets
        result['websockets'] = websockets.__version__
    except ImportError:
        result['websockets'] = None
    print(json.dumps(result, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default=str(SM))
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('presets')
    commands.add_parser('doctor')
    sync = commands.add_parser('sync')
    sync.add_argument('preset')
    for name in ('launch', 'verify'):
        p = commands.add_parser(name)
        p.add_argument('agent', choices=['claude', 'codex'])
        p.add_argument('preset')
        p.add_argument('--cwd', type=Path, default=Path.cwd())
        p.add_argument('--mode', choices=['additive', 'exclusive'], default='additive')
        p.add_argument('--executable')
        if name == 'launch':
            p.add_argument('--dry-run', action='store_true')
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if '--' in argv:
        boundary = argv.index('--')
        extra, argv = argv[boundary + 1:], argv[:boundary]
    args = parser.parse_args(argv)
    if extra and args.command != 'launch':
        parser.error('Agent arguments are allowed only for launch')
    if args.command == 'doctor':
        return doctor(args.cli)
    if args.command == 'presets':
        print(json.dumps(read_cli(args.cli, 'presets', 'list'), indent=2))
        return 0
    if getattr(args, 'mode', 'additive') == 'exclusive':
        raise Error('Exclusive skill isolation is unsupported. Use --mode additive. Global, project, and plugin skills remain inherited.')
    directory = bundle(load_preset(args.cli, args.preset), args.root)
    if args.command == 'sync':
        print(directory)
        return 0
    cwd = args.cwd.resolve(strict=True)
    if not cwd.is_dir():
        raise Error('Working directory must be a directory')
    executable = args.executable or shutil.which(args.agent)
    if not executable:
        raise Error(f'{args.agent} is not installed')
    if args.agent == 'codex' and extra:
        raise Error('Codex launch currently accepts no forwarded arguments. Configure model and permissions in the native TUI.')
    if args.agent == 'claude' and any(a.split('=')[0] in {'--bg', '--background'} for a in extra):
        raise Error('Background launch is unsupported; keep the child attached to the launcher.')
    if args.command == 'launch' and args.dry_run:
        print(json.dumps({'agent': args.agent, 'executable': executable, 'cwd': str(cwd), 'bundle': str(directory),
                          'mode': 'additive', 'mechanism': '--plugin-dir' if args.agent == 'claude' else 'private app-server + --remote',
                          'extra_args': extra, 'inherits': ['user skills', 'project skills', 'installed plugins', 'native auth/config']}, indent=2))
        return 0
    if args.agent == 'claude':
        if args.command == 'verify':
            return subprocess.call([executable, 'plugin', 'validate', '--json', str(directory)], cwd=cwd)
        return subprocess.call([executable, '--plugin-dir', str(directory), *extra], cwd=cwd)
    return codex_session(executable, directory, cwd, extra, smoke=args.command == 'verify')


def entrypoint():
    try:
        raise SystemExit(main())
    except (Error, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'sm-plugin: {exc}', file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == '__main__':
    entrypoint()
