"""Thai Voice Lab: local-only HTTP API, media storage and single-worker queue."""
import json
import logging
import os
import subprocess
import threading
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from engine import VoiceEngine
from skill_support import skill_guide
from voice_catalog import initialize_catalog

ROOT = Path(__file__).resolve().parent
DEFAULT_TEXT = 'ยินดีต้อนรับเข้าสู่ thai voice lab สร้างเสียงได้ฟรี ไม่จำกัด บนคอมพิวเตอร์เราเอง'
MAX_UPLOAD = 20 * 1024 * 1024
TERMINAL = {'completed', 'failed'}


class UploadLimitMiddleware:
    """Bound multipart bytes before Starlette parses/spools any file parts."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST' or scope.get('path') != '/api/upload':
            return await self.app(scope, receive, send)
        limit = MAX_UPLOAD + 64 * 1024  # allowance for multipart headers
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'detail': 'Content-Length ไม่ถูกต้อง'}, 400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({'detail': 'ไฟล์ต้องมีขนาดไม่เกิน 20 MB'}, 413)(scope, receive, send)
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as body:
            size = 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                size += len(chunk)
                if size > limit:
                    return await JSONResponse({'detail': 'ไฟล์ต้องมีขนาดไม่เกิน 20 MB'}, 413)(scope, receive, send)
                body.write(chunk)
                if not message.get('more_body', False):
                    break
            body.seek(0)
            delivered = False
            async def replay():
                nonlocal delivered
                if delivered:
                    return await receive()
                chunk = body.read(64 * 1024)
                more = body.tell() < size
                delivered = not more
                return {'type': 'http.request', 'body': chunk, 'more_body': more}
            await self.app(scope, replay, send)


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: str = Field(min_length=1, max_length=100)
    speed: float = Field(default=1, ge=.75, le=1.3)
    guidance: float = Field(default=2.5, ge=1, le=4)
    steps: int = Field(default=12, ge=4, le=32)

    @field_validator('text')
    @classmethod
    def nonblank(cls, text):
        if not text.strip():
            raise ValueError('กรุณาใส่ข้อความที่ต้องการสร้างเสียง')
        return text.strip()


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def create_app(data_dir=None, synthesizer=None):
    data = Path(data_dir or os.environ.get('THAI_VOICE_DATA', ROOT / 'data')).resolve()
    for directory in ['voices', 'uploads', 'outputs', 'jobs']:
        (data / directory).mkdir(parents=True, exist_ok=True)
    engine = synthesizer or VoiceEngine()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='voxcpm')
    lock = threading.RLock()
    jobs = {}
    for path in (data / 'jobs').glob('*.json'):
        try:
            job = json.loads(path.read_text(encoding='utf-8'))
            if job['status'] not in TERMINAL:
                job.update(status='failed', message='เซิร์ฟเวอร์หยุดระหว่างสร้างเสียง กรุณาลองใหม่')
                save_json(path, job)
            jobs[job['id']] = job
        except (ValueError, KeyError):
            logging.warning('Skipped invalid job record: %s', path.name)

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title='Thai Voice Lab', lifespan=lifespan)
    app.add_middleware(UploadLimitMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver', '[::1]'])
    app.state.voices = initialize_catalog(data, ROOT / 'assets' / 'voices')
    for path in (data / 'uploads').glob('*.json'):
        try:
            app.state.voices.append(json.loads(path.read_text(encoding='utf-8')))
        except ValueError:
            logging.warning('Skipped invalid upload metadata: %s', path.name)

    @app.middleware('http')
    async def local_writes(request, call_next):
        if request.method in {'POST', 'DELETE', 'PUT', 'PATCH'}:
            origin = request.headers.get('origin')
            expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
            if origin and origin != expected:
                return JSONResponse({'detail': 'คำขอต้องมาจากหน้าเว็บในเครื่องนี้'}, status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'ไม่อนุญาตคำขอจากเว็บไซต์อื่น'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-cache'
        return response

    def public_voice(voice):
        folder = 'uploads' if voice.get('kind') == 'upload' else 'voices'
        return {**voice, 'audio_url': f'/media/{folder}/{voice["filename"]}'}

    def update_job(job_id, **changes):
        with lock:
            jobs[job_id].update(changes)
            save_json(data / 'jobs' / f'{job_id}.json', jobs[job_id])

    def run_job(job_id, reference):
        started = time.monotonic()
        with lock:
            job = dict(jobs[job_id])
        output = data / 'outputs' / f'{job_id}.wav'
        try:
            engine(job['text'], reference, output, job['settings'],
                   lambda status, progress, message: update_job(job_id, status=status, progress=progress, message=message))
            wave, sr = sf.read(output, dtype='float32', always_2d=True)
            mono = np.max(np.abs(wave), axis=1)
            peaks = [round(float(np.max(x)), 4) if len(x) else 0 for x in np.array_split(mono, 120)]
            update_job(job_id, status='completed', progress=1, message='สร้างเสียงเรียบร้อย',
                       duration=round(len(wave) / sr, 2), sample_rate=sr, peaks=peaks,
                       elapsed=round(time.monotonic() - started, 1), audio_url=f'/media/outputs/{job_id}.wav')
        except Exception as exc:
            logging.exception('Voice generation failed')
            output.unlink(missing_ok=True)
            message = 'สร้างเสียงไม่สำเร็จ กรุณาลองใหม่'
            if isinstance(exc, (FileNotFoundError, OSError)):
                message = 'ไม่พบโมเดลหรือไฟล์เสียงในเครื่อง ตรวจสอบการติดตั้งและลองใหม่'
            update_job(job_id, status='failed', message=message, elapsed=round(time.monotonic() - started, 1))

    @app.get('/api/skill')
    def get_skill_guide():
        return skill_guide(ROOT)

    @app.get('/api/status')
    def status():
        with lock:
            active = sum(j['status'] not in TERMINAL for j in jobs.values())
        return {'model': 'VoxCPM2', 'state': getattr(engine, 'state', 'ready'),
                'device': getattr(engine, 'device', 'auto'), 'active_jobs': active,
                'default_text': DEFAULT_TEXT, 'local_only': True}

    @app.get('/api/voices')
    def voices():
        with lock:
            return [public_voice(v) for v in app.state.voices]

    @app.post('/api/upload', status_code=201)
    def upload(file: UploadFile = File(...)):
        file_id = uuid.uuid4().hex
        raw = data / 'uploads' / f'{file_id}.input'
        output = data / 'uploads' / f'{file_id}.wav'
        size = 0
        try:
            with raw.open('wb') as handle:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, 'ไฟล์ต้องมีขนาดไม่เกิน 20 MB')
                    handle.write(chunk)
            # Decode a bounded duration; uploaded file paths are never supplied by the client.
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe',
                            '-format_whitelist', 'wav,mp3,mov,matroska,webm,ogg,flac,aac',
                            '-i', str(raw), '-t', '30.1', '-ar', '24000', '-ac', '1', str(output)],
                           check=True, timeout=30, capture_output=True)
            wave, sr = sf.read(output, dtype='float32')
            duration = len(wave) / sr
            if duration < 3 or duration > 30:
                raise HTTPException(422, 'ใช้เสียงพูดความยาว 3–30 วินาที')
            if np.max(np.abs(wave)) < .001:
                raise HTTPException(422, 'ไฟล์นี้เบาเกินไปหรือไม่มีเสียงพูด กรุณาเลือกไฟล์ใหม่')
            # A short reference makes conditioning faster and more stable.
            reference_seconds = min(duration, 12)
            retained = wave[:int(reference_seconds * sr)]
            if np.max(np.abs(retained)) < .001:
                raise HTTPException(422, '12 วินาทีแรกไม่มีเสียงพูด กรุณาตัดช่วงเงียบต้นไฟล์แล้วลองใหม่')
            sf.write(output, retained, sr)
            voice = {'id': file_id, 'name': Path((file.filename or 'เสียงของฉัน').replace('\\', '/')).stem[:60],
                     'filename': output.name, 'kind': 'upload', 'license': 'ไฟล์ของคุณ', 'language': 'Custom',
                     'duration': round(reference_seconds, 2), 'original_duration': round(duration, 2),
                     'description': 'เสียงอ้างอิงส่วนตัว · เก็บบนเครื่องนี้'}
            with lock:
                save_json(data / 'uploads' / f'{file_id}.json', voice)
                app.state.voices.append(voice)
            return public_voice(voice)
        except HTTPException:
            output.unlink(missing_ok=True)
            raise
        except (subprocess.SubprocessError, ValueError, RuntimeError):
            output.unlink(missing_ok=True)
            raise HTTPException(422, 'อ่านไฟล์เสียงไม่ได้ กรุณาใช้ WAV, MP3, M4A, FLAC, OGG หรือ WebM')
        finally:
            raw.unlink(missing_ok=True)
            file.file.close()

    @app.post('/api/generate', status_code=202)
    def generate(request: GenerateRequest):
        with lock:
            voice = next((v for v in app.state.voices if v['id'] == request.voice_id), None)
            if not voice:
                raise HTTPException(404, 'ไม่พบเสียงที่เลือก')
            folder = 'uploads' if voice.get('kind') == 'upload' else 'voices'
            reference = data / folder / voice['filename']
            if not reference.is_file():
                raise HTTPException(404, 'ไม่พบไฟล์เสียงอ้างอิง')
            if sum(j['status'] not in TERMINAL for j in jobs.values()) >= 3:
                raise HTTPException(429, 'คิวเต็มแล้ว รอให้งานก่อนหน้าเสร็จก่อน')
            job_id = uuid.uuid4().hex
            job = {'id': job_id, 'text': request.text, 'voice_id': voice['id'], 'voice_name': voice['name'],
                   'status': 'queued', 'progress': 0, 'message': 'เข้าคิวแล้ว กำลังเตรียมโมเดล',
                   'created_at': datetime.now(timezone.utc).isoformat(),
                   'settings': {'speed': request.speed, 'steps': request.steps, 'guidance': request.guidance}}
            jobs[job_id] = job
            save_json(data / 'jobs' / f'{job_id}.json', job)
            executor.submit(run_job, job_id, reference)
            return dict(job)

    @app.get('/api/jobs/{job_id}')
    def get_job(job_id: str):
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, 'ไม่พบงานนี้')
            return dict(jobs[job_id])

    @app.get('/api/history')
    def history():
        with lock:
            return sorted((dict(j) for j in jobs.values()), key=lambda j: j['created_at'], reverse=True)[:100]

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'static' / 'index.html')

    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    for directory in ['voices', 'uploads', 'outputs']:
        # Serve only audio files; metadata and raw uploads stay private.
        def media_route(folder):
            def media(filename: str):
                if Path(filename).name != filename or not filename.endswith('.wav'):
                    raise HTTPException(404)
                path = data / folder / filename
                if not path.is_file():
                    raise HTTPException(404)
                return FileResponse(path, media_type='audio/wav', filename=filename, content_disposition_type='inline')
            return media
        app.add_api_route(f'/media/{directory}/{{filename}}', media_route(directory), methods=['GET'])
    return app


app = create_app()
