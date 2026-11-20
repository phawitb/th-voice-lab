"""Local VoxCPM2 adapter. No remote inference or runtime model downloads."""
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


def split_text(text, limit=150):
    # Prefer sentence/word boundaries; cap long unspaced Thai to bound model context.
    chunks = []
    for line in re.split(r'[\n]+|(?<=[.!?。])\s+', text.strip()):
        while len(line) > limit:
            cut = line.rfind(' ', 0, limit + 1)
            if cut < limit // 3:
                cut = limit
                while cut > 1 and 0x0E31 <= ord(line[cut]) <= 0x0E4E:
                    cut -= 1
            chunks.append(line[:cut].strip())
            line = line[cut:].strip()
        if line.strip():
            chunks.append(line.strip())
    return chunks


class VoiceEngine:
    def __init__(self):
        self.model = None
        self.state = 'idle'
        self.device = 'auto'

    def __call__(self, text, reference, output, settings, progress):
        if self.model is None:
            self.state = 'loading'
            progress('loading', 0.03, 'กำลังโหลด VoxCPM2 เข้าเครื่อง · ครั้งแรกอาจใช้เวลา 1–2 นาที')
            try:
                os.environ.setdefault('HF_HUB_OFFLINE', '1')
                os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
                import torch
                from voxcpm import VoxCPM
                self.device = 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')
                self.model = VoxCPM.from_pretrained(
                    os.environ.get('THAI_VOICE_MODEL', 'openbmb/VoxCPM2'),
                    load_denoiser=False, local_files_only=True, optimize=False, device=self.device,
                )
                self.state = 'ready'
            except Exception:
                self.state = 'error'
                raise
        sr = self.model.tts_model.sample_rate
        chunks = split_text(text)
        audio = []
        for i, chunk in enumerate(chunks):
            progress('generating', 0.08 + 0.8 * i / len(chunks), f'กำลังสร้างเสียง · ช่วงที่ {i + 1}/{len(chunks)}')
            wave = np.asarray(self.model.generate(
                text=chunk, reference_wav_path=str(reference), cfg_value=settings['guidance'],
                inference_timesteps=settings['steps'], normalize=True,
                max_len=1200, retry_badcase=True, retry_badcase_max_times=2,
            ), dtype=np.float32).reshape(-1)
            if wave.size == 0 or not np.isfinite(wave).all() or np.max(np.abs(wave)) < .0001:
                raise RuntimeError('โมเดลส่งเสียงว่างกลับมา กรุณาลองสร้างใหม่')
            active = np.flatnonzero(np.abs(wave) > .008)
            if len(active):
                wave = wave[max(0, active[0] - int(.06 * sr)):min(len(wave), active[-1] + int(.14 * sr))]
            if audio:
                audio.append(np.zeros(int(.22 * sr), np.float32))
            audio.append(wave)
        progress('processing', .92, 'กำลังปรับระดับเสียงและเตรียมไฟล์ WAV')
        raw = Path(output).with_suffix('.raw.wav')
        try:
            sf.write(raw, np.concatenate(audio), sr)
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(raw),
                            '-af', f"atempo={settings['speed']},loudnorm=I=-18:TP=-1.5:LRA=11",
                            '-ar', str(sr), '-ac', '1', '-c:a', 'pcm_s16le', str(output)],
                           check=True, timeout=120, capture_output=True)
        finally:
            raw.unlink(missing_ok=True)
        return sr
