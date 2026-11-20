import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def load(relative):
    path=ROOT/relative
    assert path.exists(),f'Missing implementation: {relative}'
    spec=importlib.util.spec_from_file_location(path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_first_install_has_eight_public_voices(tmp_path):
    module=load('voice_catalog.py')
    voices=module.initialize_catalog(tmp_path, ROOT/'assets/voices')
    assert len(voices)==8
    assert all(v['kind']=='public' and v['license']=='CC0-1.0' for v in voices)
    assert all((tmp_path/'voices'/v['filename']).is_file() for v in voices)
    assert not (tmp_path/'voices'/'mhee.wav').exists()


def test_catalog_preserves_existing_private_data(tmp_path):
    module=load('voice_catalog.py')
    original=[{'id':'personal','kind':'local','filename':'mine.wav'}]
    (tmp_path/'voices.json').write_text(json.dumps(original))
    assert module.initialize_catalog(tmp_path,ROOT/'assets/voices')==original
    assert json.loads((tmp_path/'voices.json').read_text())==original


def test_installer_plan_uses_checkout_venv_without_owner_paths(tmp_path):
    setup=load('scripts/setup.py')
    plan=setup.setup_plan(tmp_path,'codex',download_model=True)
    assert plan['project']==str(tmp_path.resolve())
    assert '.venv' in plan['runtime_python']
    assert str(Path.home()) not in json.dumps(plan)
    assert plan['model']=='openbmb/VoxCPM2'
    assert plan['target']=='codex'


def test_customer_prompts_start_from_repository():
    from skill_support import skill_guide
    guide=skill_guide('/Users/private/seller-machine')
    for name,prompt in guide['install_prompts'].items():
        assert 'https://github.com/phawitb/th-voice-lab.git' in prompt
        assert f'--target {name}' in prompt
        assert 'scripts/setup.py' in prompt and '--download-model' in prompt
        assert '/Users/private' not in prompt


def test_launcher_keeps_venv_interpreter_path(tmp_path):
    import subprocess
    import venv
    module=load('scripts/start_server.py')
    venv.EnvBuilder(with_pip=False, symlinks=True).create(tmp_path/'.venv')
    selected=module.select_python(tmp_path,{})
    prefix=subprocess.check_output([selected,'-c','import sys; print(sys.prefix)'],text=True).strip()
    assert Path(prefix)==tmp_path/'.venv'


def test_reuse_python_keeps_venv_symlink(tmp_path):
    import sys
    module=load('scripts/setup.py')
    interpreter=tmp_path/'python';interpreter.symlink_to(sys.executable)
    plan=module.setup_plan(tmp_path,'none',reuse_python=interpreter)
    assert plan['runtime_python']==str(interpreter)
