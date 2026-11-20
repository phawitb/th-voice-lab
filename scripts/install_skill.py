#!/usr/bin/env python3
"""Install the local Thai Voice Lab skill without changing agent permissions."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def install_skill(source, target, project):
    source, target, project = Path(source).resolve(), Path(target).expanduser(), Path(project).expanduser().resolve()
    if not (project / 'app.py').is_file() or not (project / 'start.sh').is_file():
        raise ValueError('Project must contain app.py and start.sh.')
    if not (source / 'SKILL.md').is_file():
        raise ValueError('Source skill is missing SKILL.md.')
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'An existing skill is preserved at {target}. Review it before updating.')
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata = {'project': str(project), 'server_url': 'http://127.0.0.1:7860'}
    with tempfile.TemporaryDirectory(prefix='.thai-voice-install-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'thai-voice-lab'
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'local.json'))
        (stage / 'local.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        stage.rename(target)
    return {**metadata, 'installed': str(target)}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['codex', 'claude', 'both'], required=True)
    parser.add_argument('--project', type=Path, default=ROOT)
    args = parser.parse_args()
    names = ['codex', 'claude'] if args.target == 'both' else [args.target]
    folders = {'codex': Path.home() / '.agents/skills/thai-voice-lab', 'claude': Path.home() / '.claude/skills/thai-voice-lab'}
    try:
        # Preflight both targets before making either change.
        for name in names:
            if folders[name].exists() or folders[name].is_symlink():
                raise FileExistsError(f'Existing {name} skill preserved: {folders[name]}')
        result = [install_skill(ROOT / 'skills/thai-voice-lab', folders[name], args.project) for name in names]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
