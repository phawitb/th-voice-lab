#!/usr/bin/env python3
"""Standard-library client for a loopback Thai Voice Lab server."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave

SKILL_DIR = Path(__file__).resolve().parents[1]


def validate_base_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'} or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
        raise ValueError('Use a loopback HTTP URL, for example http://127.0.0.1:7860')
    return url.rstrip('/')


def resolve_voice(voices, selection):
    matches = [v for v in voices if selection.casefold() in {v['id'].casefold(), v['name'].casefold()}]
    if len(matches) != 1:
        raise ValueError(f'Voice {selection!r} is missing or ambiguous. Run voices and choose an exact ID.')
    return matches[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected HTTP redirect; no request was sent to the new destination.')


class Client:
    def __init__(self, base_url):
        self.base = validate_base_url(base_url)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, payload=None, data=None, content_type=None):
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            content_type = 'application/json'
        if content_type:
            headers['Content-Type'] = content_type
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get('detail', str(exc))
            except (ValueError, OSError):
                detail = str(exc)
            raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if data is not None:
                raise RuntimeError('POST result is uncertain. Do not resubmit automatically. Inspect history to find the accepted job/upload first.') from exc
            raise RuntimeError('Local server unavailable. Run start with the configured project, then retry this read.') from exc

    def upload(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('Reference must be an existing audio file no larger than 20 MB.')
        boundary = 'voice-lab-' + uuid.uuid4().hex
        # Fixed multipart filename avoids interpreting a local name as a header.
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="reference{path.suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        return self.request('/api/upload', data=data, content_type=f'multipart/form-data; boundary={boundary}')

    def download(self, job, output, overwrite=False):
        expected = f'/media/outputs/{job["id"]}.wav'
        if job.get('audio_url') != expected or not all(c in '0123456789abcdef' for c in job['id']) or len(job['id']) != 32:
            raise ValueError('Unexpected output URL; refusing download.')
        output = Path(output).expanduser().resolve()
        if output.exists() and not overwrite:
            raise FileExistsError(f'Output already exists: {output}')
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.wav', delete=False) as handle:
            temporary = Path(handle.name)
            try:
                with self.opener.open(self.base + expected, timeout=60) as response:
                    shutil.copyfileobj(response, handle)
                handle.close()
                with wave.open(str(temporary), 'rb') as audio:
                    if not audio.getnframes():
                        raise ValueError('Downloaded WAV is empty')
                if overwrite:
                    os.replace(temporary, output)
                else:
                    # Atomic no-clobber installation on the same filesystem.
                    os.link(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        return str(output)


def config():
    path = SKILL_DIR / 'local.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def start_server(client, project=None):
    try:
        status = client.request('/api/status')
    except RuntimeError:
        status = None
    if status is not None:
        if status.get('model') != 'VoxCPM2' or status.get('local_only') is not True:
            raise ValueError('Port is occupied by an unexpected service; it was not changed.')
        return status
    candidate = project or os.environ.get('THAI_VOICE_LAB_PROJECT') or config().get('project')
    if not candidate:
        source_project = SKILL_DIR.parent.parent
        if (source_project / 'app.py').is_file():
            candidate = str(source_project)
    if not candidate:
        raise ValueError('Project not configured. Run start --project /absolute/path/to/th-voice-lab')
    root = Path(candidate).expanduser().resolve()
    if not (root / 'app.py').is_file() or not (root / 'start.sh').is_file():
        raise ValueError('Project must contain app.py and start.sh.')
    (root / 'data').mkdir(exist_ok=True)
    env = os.environ.copy()
    env['PORT'] = str(urllib.parse.urlsplit(client.base).port or 80)
    with (root / 'data' / 'skill-server.log').open('ab') as log:
        launcher = root / 'scripts/start_server.py'
        command = [sys.executable, str(launcher)] if launcher.is_file() else [str(root / 'start.sh')]
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Server exited. Read {root / "data/skill-server.log"}.')
        time.sleep(.5)
        try:
            return client.request('/api/status')
        except RuntimeError:
            pass
    raise RuntimeError(f'Startup not yet confirmed; inspect {root / "data/skill-server.log"} before starting another server.')


def wait_job(client, job_id, timeout):
    deadline, previous = time.monotonic() + timeout, None
    while True:
        job = client.request('/api/jobs/' + urllib.parse.quote(job_id, safe=''))
        state = (job['status'], job.get('message'))
        if state != previous:
            print(f'{job_id}: {job.get("message", job["status"])}', file=sys.stderr, flush=True)
            previous = state
        if job['status'] in {'completed', 'failed'}:
            return job
        if time.monotonic() >= deadline:
            return {**job, 'wait_timed_out': True, 'note': 'Job is still running. Resume with wait --job ID; do not submit again.'}
        time.sleep(min(2, max(.01, deadline - time.monotonic())))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('THAI_VOICE_LAB_URL', 'http://127.0.0.1:7860'))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status'); sub.add_parser('voices'); sub.add_parser('history')
    start = sub.add_parser('start'); start.add_argument('--project')
    upload = sub.add_parser('upload'); upload.add_argument('file')
    gen = sub.add_parser('generate')
    text = gen.add_mutually_exclusive_group(required=True)
    text.add_argument('--text'); text.add_argument('--text-file')
    reference = gen.add_mutually_exclusive_group()
    reference.add_argument('--voice', default=None); reference.add_argument('--reference')
    gen.add_argument('--speed', type=float, default=1)
    gen.add_argument('--steps', type=int, choices=[8, 12, 24], default=12)
    wait = sub.add_parser('wait'); wait.add_argument('--job', required=True)
    for command in [gen, wait]:
        command.add_argument('--output', required=True)
        command.add_argument('--timeout', type=float, default=600)
        command.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    owned_lock = None
    try:
        client = Client(args.url)
        if args.command in {'status', 'voices', 'history'}:
            result = client.request('/api/' + args.command)
        elif args.command == 'start':
            result = start_server(client, args.project)
        elif args.command == 'upload':
            result = client.upload(args.file)
        else:
            output = Path(args.output).expanduser().resolve()
            if output.suffix.lower() != '.wav':
                raise ValueError('Output must use the .wav extension.')
            if output.exists() and not args.overwrite:
                raise FileExistsError(f'Output already exists: {output}. Choose a new name or pass --overwrite explicitly.')
            if args.timeout <= 0:
                raise ValueError('Timeout must be positive.')
            if args.command == 'generate':
                text = Path(args.text_file).expanduser().read_text(encoding='utf-8') if args.text_file else args.text
                if not text.strip() or len(text) > 2000 or not .75 <= args.speed <= 1.3:
                    raise ValueError('Text must contain 1–2000 characters; speed must be 0.75–1.30.')
                receipt = output.with_suffix('.job.json')
                output.parent.mkdir(parents=True, exist_ok=True)
                lock_path = output.with_suffix('.submit.lock')
                try:
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    raise FileExistsError(f'Another submission owns {lock_path}. Inspect the receipt/history; do not submit a duplicate.')
                owned_lock = lock_path
                with os.fdopen(descriptor, 'w') as lock_file:
                    lock_file.write(str(os.getpid()))
                if receipt.exists() and not args.overwrite:
                    raise FileExistsError(f'Job receipt exists: {receipt}. Inspect it and resume with wait instead of creating a duplicate.')
                receipt_data = {'status': 'submitting', 'url': client.base, 'output': str(output), 'text': text,
                                'voice': args.voice or ('uploaded-reference' if args.reference else 'thai-01'), 'created_at': time.time()}
                # Retain this reservation even on an uncertain POST outcome.
                receipt.write_text(json.dumps(receipt_data, ensure_ascii=False, indent=2), encoding='utf-8')
                voice = client.upload(args.reference) if args.reference else resolve_voice(client.request('/api/voices'), args.voice or 'thai-01')
                job = client.request('/api/generate', payload={'text': text, 'voice_id': voice['id'], 'speed': args.speed, 'steps': args.steps})
                print(json.dumps({'job_id': job['id'], 'receipt': str(receipt)}, ensure_ascii=False), file=sys.stderr, flush=True)
                receipt_data.update(status='accepted', job_id=job['id'], voice_id=voice['id'])
                with tempfile.NamedTemporaryFile(mode='w', dir=output.parent, delete=False, encoding='utf-8') as handle:
                    json.dump(receipt_data, handle, ensure_ascii=False, indent=2)
                    receipt_temporary = Path(handle.name)
                try:
                    os.replace(receipt_temporary, receipt)
                finally:
                    receipt_temporary.unlink(missing_ok=True)
                job_id = job['id']
            else:
                job_id = args.job
            result = wait_job(client, job_id, args.timeout)
            if result['status'] == 'completed':
                result['output_file'] = client.download(result, output, args.overwrite)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 2 if result.get('wait_timed_out') else 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if owned_lock is not None:
            owned_lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
