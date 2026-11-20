#!/usr/bin/env python3
"""Bundle only the skill, installer and guide; never package recordings/models."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'skills'/'thai-voice-lab'
output=ROOT/'static'/'downloads'/'thai-voice-lab-skill.zip'
output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.name!='local.json' and path.suffix!='.pyc':
            archive.write(path,Path('thai-voice-lab-skill')/path.relative_to(ROOT))
    archive.write(ROOT/'scripts/install_skill.py','thai-voice-lab-skill/scripts/install_skill.py')
    archive.write(source/'references/installation.md','thai-voice-lab-skill/INSTALL.md')
print(output)
