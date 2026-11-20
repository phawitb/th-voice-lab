import importlib
import io
import time
import numpy as np
import soundfile as sf
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def isolated_default_storage(tmp_path, monkeypatch):
    monkeypatch.setenv('THAI_VOICE_DATA', str(tmp_path / 'bootstrap'))


@pytest.fixture
def client(tmp_path):
    module = importlib.import_module('app')
    def synth(text, reference, output, settings, progress):
        progress('generating', 0.5, 'กำลังสร้างเสียง')
        sf.write(output, np.sin(np.arange(24000) * 0.04) * .1, 24000)
        return 24000
    app = module.create_app(data_dir=tmp_path, synthesizer=synth)
    (tmp_path / 'voices' / 'sample.wav').write_bytes(wav())
    app.state.voices = [{'id':'sample','name':'Sample','filename':'sample.wav','kind':'public','license':'CC0-1.0'}]
    with TestClient(app) as c:
        yield c

def wav(seconds=4):
    buf=io.BytesIO(); sf.write(buf,np.sin(np.arange(int(24000*seconds))*.04)*.1,24000,format='WAV'); return buf.getvalue()

def test_empty_and_unknown_voice_rejected(client):
    assert client.post('/api/generate',json={'text':' ','voice_id':'sample'}).status_code==422
    assert client.post('/api/generate',json={'text':'สวัสดี','voice_id':'missing'}).status_code==404
    assert client.post('/api/generate',json={'text':'a'*2001,'voice_id':'sample'}).status_code==422

def test_generate_history_and_audio(client):
    response=client.post('/api/generate',json={'text':'สวัสดีครับ','voice_id':'sample'})
    assert response.status_code==202
    job=response.json()
    for _ in range(100):
        job=client.get('/api/jobs/'+job['id']).json()
        if job['status'] in ('completed','failed'): break
        time.sleep(.02)
    assert job['status']=='completed',job
    assert job['duration'] == 1
    assert client.get(job['audio_url']).content[:4]==b'RIFF'
    assert client.get('/api/history').json()[0]['id']==job['id']

def test_upload_is_decoded_and_path_is_generated(client):
    r=client.post('/api/upload',files={'file':('../../test.wav',wav(),'audio/wav')})
    assert r.status_code==201,r.text
    assert '..' not in r.json()['filename']
    assert r.json()['duration']==4
    assert client.get('/api/voices').json()[-1]['id']==r.json()['id']

def test_invalid_and_short_audio_rejected(client):
    assert client.post('/api/upload',files={'file':('bad.wav',b'not audio','audio/wav')}).status_code==422
    assert client.post('/api/upload',files={'file':('short.wav',wav(.1),'audio/wav')}).status_code==422

def test_cross_origin_write_and_host_rejected(client):
    assert client.post('/api/generate',headers={'Origin':'https://evil.example'},json={'text':'สวัสดี','voice_id':'sample'}).status_code==403
    assert client.get('/api/status',headers={'Host':'evil.example'}).status_code==400

def test_settings_and_missing_job_rejected(client):
    assert client.post('/api/generate',json={'text':'สวัสดี','voice_id':'sample','speed':99}).status_code==422
    assert client.get('/api/jobs/not-a-job').status_code==404


def test_uploaded_playlist_cannot_read_local_audio(client, tmp_path):
    secret = tmp_path / "private.wav"
    secret.write_bytes(wav())
    playlist = f"ffconcat version 1.0\nfile '{secret}'\n".encode()
    result = client.post('/api/upload',files={'file':('voice.wav',playlist,'audio/wav')})
    assert result.status_code == 422


def test_reference_must_contain_sound_in_retained_segment(client):
    buf=io.BytesIO()
    wave=np.concatenate([np.zeros(13*24000),np.sin(np.arange(3*24000)*.04)*.1])
    sf.write(buf,wave,24000,format='WAV')
    response=client.post('/api/upload',files={'file':('late.wav',buf.getvalue(),'audio/wav')})
    assert response.status_code==422


def test_upload_limit_before_multipart_parsing(client):
    # Invalid multipart would return 400/422 if parsed before the size check.
    r=client.post('/api/upload',content=b'bad',headers={'Content-Type':'multipart/form-data; boundary=x','Content-Length':str(21*1024*1024)})
    assert r.status_code==413


def test_upload_chunked_body_is_bounded(client):
    r=client.post('/api/upload',content=iter([b'x'*(1024*1024)]*21),headers={'Content-Type':'multipart/form-data; boundary=x'})
    assert r.status_code==413


def test_restart_preserves_completed_history_and_marks_interrupted(tmp_path):
    import app as module
    import json
    (tmp_path/'jobs').mkdir()
    for job_id,status in [('done','completed'),('interrupted','generating')]:
        (tmp_path/'jobs'/f'{job_id}.json').write_text(json.dumps({'id':job_id,'status':status,'created_at':'2026-11-20T12:00:00Z'}))
    with TestClient(module.create_app(data_dir=tmp_path)) as client:
        assert client.get('/api/jobs/done').json()['status']=='completed'
        assert client.get('/api/jobs/interrupted').json()['status']=='failed'
        assert len(client.get('/api/history').json())==2


def test_model_failure_releases_queue(tmp_path):
    import app as module
    def failing(*args):
        raise RuntimeError('model failed')
    application=module.create_app(data_dir=tmp_path,synthesizer=failing)
    (tmp_path/'voices'/'sample.wav').write_bytes(wav())
    application.state.voices=[{'id':'sample','name':'Sample','filename':'sample.wav','kind':'public'}]
    with TestClient(application) as client:
        for _ in range(4):
            r=client.post('/api/generate',json={'text':'ทดสอบ','voice_id':'sample'})
            assert r.status_code==202
            for _ in range(100):
                j=client.get('/api/jobs/'+r.json()['id']).json()
                if j['status']=='failed':break
                time.sleep(.01)
            assert j['status']=='failed'
        assert client.get('/api/status').json()['active_jobs']==0


@pytest.mark.parametrize('extension', ['mp3','m4a','flac','ogg','webm'])
def test_supported_audio_formats(client, tmp_path, extension):
    import subprocess
    source=tmp_path/'source.wav';source.write_bytes(wav())
    encoded=tmp_path/f'reference.{extension}'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),str(encoded)],check=True)
    r=client.post('/api/upload',files={'file':(encoded.name,encoded.read_bytes(),'application/octet-stream')})
    assert r.status_code==201,r.text
    assert abs(r.json()['duration']-4)<.1


def test_skill_guide_has_copyable_commands_and_download(client):
    r=client.get('/api/skill')
    assert r.status_code==200
    guide=r.json()
    assert '--target codex' in guide['install_prompts']['codex']
    assert '--target claude' in guide['install_prompts']['claude']
    assert '$thai-voice-lab' in guide['examples']['codex']
    assert guide['download_url']=='/static/downloads/thai-voice-lab-skill.zip'


def test_generation_writes_utf8_even_with_legacy_system_encoding(client, monkeypatch):
    from pathlib import Path
    original=Path.write_text
    def legacy_write(path,text,*args,**kwargs):
        if kwargs.get('encoding') is None:
            text.encode('cp1252')
        return original(path,text,*args,**kwargs)
    monkeypatch.setattr(Path,'write_text',legacy_write)
    r=client.post('/api/generate',json={'text':'สวัสดีครับ','voice_id':'sample'})
    assert r.status_code==202
