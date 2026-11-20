import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def load(relative):
    path=ROOT/relative
    assert path.exists(),f'Missing implementation: {relative}'
    spec=importlib.util.spec_from_file_location(path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_client_rejects_remote_destinations():
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    for url in ['https://example.com','http://127.0.0.1.evil.test:7860','http://user:secret@localhost:7860','file:///tmp/x']:
        with pytest.raises(ValueError):client.validate_base_url(url)
    assert client.validate_base_url('http://127.0.0.1:7860/')=='http://127.0.0.1:7860'


def test_voice_resolution_never_silently_substitutes():
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    voices=[{'id':'thai-01','name':'เสียงไทย 01'},{'id':'mhee','name':'Mhee'}]
    assert client.resolve_voice(voices,'เสียงไทย 01')['id']=='thai-01'
    assert client.resolve_voice(voices,'MHEE')['id']=='mhee'
    with pytest.raises(ValueError):client.resolve_voice(voices,'unknown')


def test_installer_preserves_existing_skill_and_stores_project(tmp_path):
    installer=load('scripts/install_skill.py')
    target=tmp_path/'skills'/'thai-voice-lab'
    result=installer.install_skill(ROOT/'skills'/'thai-voice-lab',target,ROOT)
    assert (target/'SKILL.md').exists()
    assert result['project']==str(ROOT)
    (target/'custom.txt').write_text('keep me')
    with pytest.raises(FileExistsError):installer.install_skill(ROOT/'skills'/'thai-voice-lab',target,ROOT)
    assert (target/'custom.txt').read_text()=='keep me'


def test_installer_rejects_wrong_project(tmp_path):
    installer=load('scripts/install_skill.py')
    with pytest.raises(ValueError):installer.install_skill(ROOT/'skills'/'thai-voice-lab',tmp_path/'target',tmp_path)


def test_existing_output_rejected_before_any_submission(tmp_path,monkeypatch):
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    out=tmp_path/'existing.wav';out.write_bytes(b'preserve')
    def fail_request(*args,**kwargs):
        pytest.fail('No request should be submitted when output already exists')
    monkeypatch.setattr(client.Client,'request',fail_request)
    assert client.main(['generate','--text','ทดสอบ','--output',str(out)])==1
    assert out.read_bytes()==b'preserve'


def test_receipt_prevents_duplicate_generation(tmp_path,monkeypatch):
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    out=tmp_path/'pending.wav';out.with_suffix('.job.json').write_text('{"job_id":"existing"}')
    def fail_request(*args,**kwargs):
        pytest.fail('Receipt requires resuming, not another submission')
    monkeypatch.setattr(client.Client,'request',fail_request)
    assert client.main(['generate','--text','ทดสอบ','--output',str(out)])==1


def test_wait_timeout_retains_original_job():
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    class Pending:
        def request(self,path):
            assert path=='/api/jobs/original'
            return {'id':'original','status':'generating','message':'working'}
    job=client.wait_job(Pending(),'original',.001)
    assert job['id']=='original' and job['wait_timed_out'] is True


def test_bundle_excludes_local_configuration_and_audio():
    import zipfile
    bundle=ROOT/'static/downloads/thai-voice-lab-skill.zip'
    with zipfile.ZipFile(bundle) as archive:
        names=archive.namelist()
        assert any(n.endswith('SKILL.md') for n in names)
        assert any(n.endswith('scripts/install_skill.py') for n in names)
        assert not any(n.endswith(('local.json','.wav','.mp3','.safetensors','.pyc')) for n in names)


def test_concurrent_commands_only_submit_one_job(tmp_path,monkeypatch):
    import concurrent.futures
    import threading
    import time
    client=load('skills/thai-voice-lab/scripts/voice_lab.py')
    submitted=[];ready=threading.Barrier(2)
    def request(self,path,**kwargs):
        if path=='/api/voices':
            time.sleep(.04)
            return [{'id':'thai-01','name':'เสียงไทย 01'}]
        if path=='/api/generate':
            submitted.append('a'*32)
            return {'id':'a'*32}
        raise AssertionError(path)
    monkeypatch.setattr(client.Client,'request',request)
    monkeypatch.setattr(client,'wait_job',lambda *args:{'id':'a'*32,'status':'generating','wait_timed_out':True})
    def run():
        ready.wait()
        return client.main(['generate','--text','ทดสอบ','--output',str(tmp_path/'same.wav')])
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:run(),range(2)))
    assert len(submitted)==1
    assert sorted(results)==[1,2]
