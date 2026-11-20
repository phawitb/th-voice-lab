#!/usr/bin/env python3
"""Prepare a customer checkout, cached model and local agent skill (stdlib only)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'openbmb/VoxCPM2'
MODEL_REVISION = '7936080b41163874f38610f46f438e2c0757f9fd'


def setup_plan(project, target, download_model=False, reuse_python=None):
    root = Path(project).expanduser().resolve()
    runtime = str(Path(reuse_python).expanduser().absolute()) if reuse_python else str(root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
    return {'project': str(root), 'target': target, 'runtime_python': runtime,
            'reuse_environment': bool(reuse_python), 'model': MODEL, 'revision': MODEL_REVISION,
            'download_model': download_model, 'public_reference_count': 8}


def run(command, **kwargs):
    print('+ ' + ' '.join(str(x) for x in command), flush=True)
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def prepare_environment(root, runtime, reuse=False):
    version = subprocess.check_output([str(runtime if reuse else sys.executable), '-c', 'import sys,json; print(json.dumps(list(sys.version_info[:2])))'], text=True)
    major, minor = json.loads(version)
    if major != 3 or not 11 <= minor <= 13:
        raise ValueError('Use Python 3.11–3.13 (3.12 recommended) to run setup; these dependency pins require Python >=3.11.')
    if not shutil.which('ffmpeg'):
        raise ValueError('ffmpeg is missing from PATH. Install it first (macOS: brew install ffmpeg; Ubuntu: sudo apt install ffmpeg), then rerun setup.')
    if reuse:
        return
    environment = root / '.venv'
    marker = environment / '.thai-voice-lab-managed'
    digest = hashlib.sha256((root / 'requirements.txt').read_bytes()).hexdigest()
    if environment.exists() and not marker.exists():
        raise ValueError('An existing unmanaged .venv is preserved. Use --reuse-python with its Python after checking dependencies, or choose a new checkout.')
    if not environment.exists():
        run([sys.executable, '-m', 'venv', environment])
        marker.write_text('pending')
    if marker.read_text().strip() != digest:
        run([runtime, '-m', 'pip', 'install', '-r', root / 'requirements.txt'])
        marker.write_text(digest)


def verify_runtime(runtime):
    code = '''import json,importlib.metadata as m
import fastapi,uvicorn,multipart,numpy,soundfile,torch,voxcpm
print(json.dumps({'device':'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu'),'python':__import__('sys').version.split()[0],'voxcpm':m.version('voxcpm'),'torch':torch.__version__}))'''
    result = subprocess.run([str(runtime), '-c', code], check=True, text=True, capture_output=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def prepare_model(runtime, download):
    code = '''import json,sys
from pathlib import Path
from huggingface_hub import snapshot_download
path=Path(snapshot_download(repo_id=sys.argv[1],revision=sys.argv[2],local_files_only=sys.argv[3]!='download'))
required=['model.safetensors','audiovae.pth','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','tokenization_voxcpm2.py']
missing=[name for name in required if not (path/name).is_file()]
if missing: raise RuntimeError('Incomplete model cache: '+', '.join(missing))
print(json.dumps({'model_path':str(path)}))'''
    env = os.environ.copy()
    if download:
        env.pop('HF_HUB_OFFLINE', None)
    result = subprocess.run([str(runtime), '-c', code, MODEL, MODEL_REVISION, 'download' if download else 'cached'],
                            check=True, text=True, stdout=subprocess.PIPE, env=env)
    return json.loads(result.stdout.strip().splitlines()[-1])['model_path']


def install_agents(root, target):
    if target == 'none':
        return []
    from install_skill import install_skill
    folders = {'codex': Path.home() / '.agents/skills/thai-voice-lab', 'claude': Path.home() / '.claude/skills/thai-voice-lab'}
    names = ['codex', 'claude'] if target == 'both' else [target]
    selected = []
    for name in names:
        folder = folders[name]
        if folder.exists() or folder.is_symlink():
            config = folder / 'local.json'
            configured = json.loads(config.read_text(encoding='utf-8')).get('project') if config.is_file() else None
            if configured != str(root) or not (folder / 'SKILL.md').is_file():
                raise FileExistsError(f'Existing {name} skill preserved: {folder}. Inspect it before changing its project or updating it.')
        selected.append((name, folder))
    result = []
    for name, folder in selected:
        if folder.exists():
            result.append({'target': name, 'path': str(folder), 'status': 'existing skill preserved'})
        else:
            installed = install_skill(root / 'skills/thai-voice-lab', folder, root)
            result.append({'target': name, 'path': installed['installed'], 'status': 'installed'})
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=['codex', 'claude', 'both', 'none'])
    parser.add_argument('--download-model', action='store_true', help='Allow the initial several-GB model download; cached files are reused.')
    parser.add_argument('--reuse-python', type=Path, help='Use and verify an existing environment without installing packages into it.')
    parser.add_argument('--plan', action='store_true', help='Print intended setup without changing files or downloading.')
    args = parser.parse_args()
    plan = setup_plan(ROOT, args.target, args.download_model, args.reuse_python)
    if args.plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return 0
    try:
        runtime = Path(plan['runtime_python'])
        prepare_environment(ROOT, runtime, bool(args.reuse_python))
        print('Checking installed dependencies…', flush=True)
        details = verify_runtime(runtime)
        print('Preparing VoxCPM2 (cached files are reused; a first download can be several GB)…', flush=True)
        model_path = prepare_model(runtime, args.download_model)
        sys.path.insert(0, str(ROOT))
        from voice_catalog import initialize_catalog
        voices = initialize_catalog(ROOT / 'data', ROOT / 'assets/voices')
        # Saved only locally, never included in Git or the downloadable skill.
        config = {'python': str(runtime), 'model_path': model_path, 'model_revision': MODEL_REVISION}
        (ROOT / '.runtime.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
        installed = install_agents(ROOT, args.target)
        print(json.dumps({'status': 'ready', **details, 'voices': len(voices), 'skills': installed,
                          'next': f'{sys.executable} scripts/start_server.py'}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Setup did not complete: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        if not args.download_model:
            print('If the model is not cached, rerun with --download-model to allow its download.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
