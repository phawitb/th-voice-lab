# Customer installation and prompts

## New customer machine

Source: **https://github.com/phawitb/th-voice-lab.git**. Installation includes both the app/model runtime and the agent skill. Installing just SKILL.md is insufficient. Use a local Codex or Claude Code session with filesystem and terminal access.

Ask the agent:

> ติดตั้ง Thai Voice Lab และสกิลบนเครื่องฉันจาก https://github.com/phawitb/th-voice-lab.git อ่าน README.md ก่อน ตรวจ Python 3.11–3.13, Git และ ffmpeg และช่วยติดตั้งสิ่งที่ขาด เลือกโฟลเดอร์ใหม่ที่ไม่ทับงานเดิมแล้ว clone รีโป สำหรับ Codex รัน `python3 scripts/setup.py --target codex --download-model` หรือสำหรับ Claude Code ใช้ `--target claude` จากนั้นเปิดเซิร์ฟเวอร์ด้วย `python3 scripts/start_server.py` ตรวจ status และเสียงตัวอย่าง 8 เสียง สร้างข้อความทดสอบเป็น WAV แล้วเปิดเว็บให้ลอง ไม่เขียนทับสกิลหรือข้อมูลเดิมของฉัน

Manual equivalent (use Python 3.11–3.13; 3.12 recommended):

```sh
git clone https://github.com/phawitb/th-voice-lab.git
cd th-voice-lab
python3 scripts/setup.py --target codex --download-model
python3 scripts/start_server.py
```

Use `claude` or `both` instead of `codex` as appropriate; `none` installs only the app/runtime. On Windows use `py -3.12` instead of `python3` if needed. Install ffmpeg and Git through the system's package manager first. See the repository README for platform instructions.

Setup creates a separate project `.venv`, installs requirements, downloads the pinned openbmb/VoxCPM2 snapshot (several GB on first use; existing cache is reused), initializes eight CC0 voices, stores the runtime in ignored `.runtime.json`, and installs the selected agent skill. It does not run paid TTS APIs or alter agent permissions. New environments may require substantial storage; CPU-only inference can be slow. The tested platform is macOS/Apple Silicon; do not promise a particular GPU or Windows setup is validated.

The server binds to http://127.0.0.1:7860. Check it before claiming success, then generate a short actual sample. If download or dependency installation fails, report the actual cause and remaining step. Never call a `--plan` run a completed installation. `--reuse-python /absolute/path/to/python` verifies and reuses an existing compatible environment without installing packages into it.

## Existing project / skill-only install

If the app and model already work:

```sh
python3 scripts/install_skill.py --target codex --project /actual/path/to/th-voice-lab
python3 scripts/install_skill.py --target claude --project /actual/path/to/th-voice-lab
```

Codex discovery: `~/.agents/skills/thai-voice-lab`. Claude Code discovery: `~/.claude/skills/thai-voice-lab`. The installer records the actual app path in `local.json`. If a skill already exists it is preserved; inspect it before any authorized update. `setup.py` can be rerun and preserves skills already configured for the same checkout. Reopen the agent session if the skill is not visible.

## ZIP delivery

The ZIP contains `skills/thai-voice-lab/`, `scripts/install_skill.py`, and this guide. It does **not** contain the app, dependencies, model weights or recordings. A new customer should clone the repository and run setup first. Alternatively, extract the ZIP and use its installer with `--project` pointing to an already-working app checkout. Do not imply that uploading the ZIP to a cloud chat makes the local model available there.

## Ready-to-use prompts

Codex:

> ใช้ $thai-voice-lab สร้างเสียงข้อความ “ยินดีต้อนรับเข้าสู่ thai voice lab สร้างเสียงได้ฟรี ไม่จำกัด บนคอมพิวเตอร์เราเอง” ด้วยเสียงไทย 01 บันทึกเป็น welcome.wav แล้วส่งไฟล์ให้ฟัง

Claude Code:

> /thai-voice-lab อ่านไฟล์ script.txt ด้วยเสียงไทย 02 ความเร็ว 0.95 บันทึกเป็น narration.wav และรอจนเสร็จ

Own reference:

> ใช้ skill thai-voice-lab สร้างเสียงจาก script.txt โดยใช้ my-voice.wav ที่ฉันมีสิทธิ์ใช้เป็นเสียงอ้างอิง บันทึกเป็น my-narration.wav แล้วส่งไฟล์ให้ฟัง

Resume:

> ใช้ skill thai-voice-lab อ่าน welcome.job.json แล้วรอรับงานเดิมจนเสร็จ ไม่ต้องสร้างงานใหม่

[Codex skill documentation](https://learn.chatgpt.com/docs/build-skills) · [Claude Code skill documentation](https://code.claude.com/docs/en/skills)
