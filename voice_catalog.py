"""Initialize a customer's catalogue from distributable public reference assets."""
import json
from pathlib import Path
import shutil
import tempfile


def initialize_catalog(data_dir, bundled_dir):
    data_dir, bundled_dir = Path(data_dir), Path(bundled_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = data_dir / 'voices.json'
    if manifest.exists():
        return json.loads(manifest.read_text(encoding='utf-8'))
    voices = json.loads((bundled_dir / 'manifest.json').read_text(encoding='utf-8'))
    target = data_dir / 'voices'
    target.mkdir(exist_ok=True)
    for voice in voices:
        name = voice['filename']
        if voice.get('kind') != 'public' or voice.get('license') != 'CC0-1.0' or Path(name).name != name:
            raise ValueError('The bundled catalogue must contain only public CC0 references.')
        if not (target / name).exists():
            shutil.copy2(bundled_dir / name, target / name)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=data_dir, delete=False) as handle:
        json.dump(voices, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    try:
        temporary.replace(manifest)
    finally:
        temporary.unlink(missing_ok=True)
    return voices
