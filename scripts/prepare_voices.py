"""Download eight distinct CC0 Thai speakers from Common Voice 17.0.
Uses streaming tar traversal: no full corpus is stored. Re-run explicitly to refresh.
"""
import csv
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
VOICES = ROOT / 'assets' / 'voices'
SOURCES = VOICES / 'sources'
SOURCES.mkdir(parents=True, exist_ok=True)
BASE = 'https://huggingface.co/datasets/fsicoli/common_voice_17_0'
ARCHIVE = BASE + '/resolve/main/audio/th/test/th_test_0.tar'

def fetch(url, path):
    subprocess.run(['curl','--fail','-L','--retry','2','--max-time','120','-sS',url,'-o',str(path)],check=True)

transcript = SOURCES / 'test.tsv'
if not transcript.exists():
    fetch(BASE+'/resolve/main/transcript/th/test.tsv',transcript)
rows = {r['path']:r for r in csv.DictReader(transcript.open(encoding='utf-8'),delimiter='\t')}
fetch(BASE+'/raw/main/README.md',SOURCES/'dataset-card.md')
voices, seen = [], set()
process = subprocess.Popen(['curl','--fail','-L','--retry','2','--max-time','300','-sS',ARCHIVE],stdout=subprocess.PIPE)
try:
    with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
        for member in archive:
            name=Path(member.name).name
            row=rows.get(name)
            if not member.isfile() or not row or row['client_id'] in seen or not 25<=len(row['sentence'])<=115 or int(row['down_votes'] or '0')>0: continue
            raw=archive.extractfile(member).read()
            src=SOURCES/name;src.write_bytes(raw)
            try:
                wave,sr=sf.read(src,dtype='float32')
                duration=len(wave)/sr
                if not 3.5<=duration<=11.5:
                    src.unlink();continue
                num=len(voices)+1
                filename=f'thai-{num:02d}.wav'
                subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-ar','24000','-ac','1','-af','loudnorm=I=-20:TP=-2:LRA=11',str(VOICES/filename)],check=True)
                voice={'id':f'thai-{num:02d}','name':f'เสียงไทย {num:02d}','filename':filename,'kind':'public','language':'Thai','license':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/','duration':round(duration,2),'transcript':row['sentence'],'source_clip':name,'source_url':BASE+'/blob/main/audio/th/test/th_test_0.tar','dataset_url':BASE,'source_archive_url':ARCHIVE,'source_sha256':hashlib.sha256(raw).hexdigest(),'speaker_fingerprint':hashlib.sha256(row['client_id'].encode()).hexdigest(),'description':'Common Voice 17.0 · ผู้พูดภาษาไทย'}
                voices.append(voice);seen.add(row['client_id']);print(f"Saved {voice['name']}: {duration:.2f}s {row['sentence']}",flush=True)
                if len(voices)==8:break
            except Exception:
                src.unlink(missing_ok=True);raise
finally:
    process.terminate();process.stdout.close();process.wait()
if len(voices)!=8: raise RuntimeError(f'Found only {len(voices)} distinct speakers')
(VOICES/'manifest.json').write_text(json.dumps(voices,ensure_ascii=False,indent=2),encoding='utf-8')
# Retain only selected provenance, not the full corpus speaker metadata.
transcript.unlink()
print(f'Prepared {len(voices)} references; 8 distinct public CC0 voices.',flush=True)
