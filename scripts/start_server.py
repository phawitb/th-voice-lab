#!/usr/bin/env python3
"""Launch the configured local runtime on macOS, Linux or Windows."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def runtime_config(project=ROOT):
    path = Path(project) / '.runtime.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def select_python(project=ROOT, environ=None):
    env = os.environ if environ is None else environ
    configured = runtime_config(project)
    candidates = [env.get('THAI_VOICE_PYTHON'), configured.get('python'),
                  str(Path(project) / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')),
                  str(Path.home() / 'miniforge3/bin/python3'), sys.executable]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).expanduser().absolute())
    raise RuntimeError('Run scripts/setup.py first, or set THAI_VOICE_PYTHON.')


def main():
    runtime = select_python()
    config = runtime_config()
    env = os.environ.copy()
    env['HF_HUB_OFFLINE'] = '1'
    env['PYTHONUTF8'] = '1'
    env['TOKENIZERS_PARALLELISM'] = 'false'
    if config.get('model_path'):
        env.setdefault('THAI_VOICE_MODEL', config['model_path'])
    port = int(env.get('PORT', '7860'))
    if not 1 <= port <= 65535:
        raise ValueError('PORT must be between 1 and 65535')
    os.chdir(ROOT)
    os.execve(runtime, [runtime, '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', str(port)], env)


if __name__ == '__main__':
    main()
