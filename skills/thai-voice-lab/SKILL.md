---
name: thai-voice-lab
description: Use when the user wants local Thai text-to-speech, a Thai narration WAV, or voice-reference generation with Thai Voice Lab and VoxCPM2, including สร้างเสียงไทย and พากย์เสียงในเครื่อง. Also applies to installing or operating this local voice skill, not unrelated video production.
---

# Thai Voice Lab

Create Thai speech with the user's local VoxCPM2 server. Use the bundled standard-library client; do not rebuild the app, load a second model instance, or substitute a cloud TTS service.

## Run

Resolve `scripts/voice_lab.py` relative to this SKILL.md, regardless of the working directory. Use an available Python 3.10+ interpreter. The client does not need third-party packages.

1. Run `python3 <skill-dir>/scripts/voice_lab.py start`. This reuses the server or starts the existing project configured in `local.json`. For a new customer or missing project, follow [installation.md](references/installation.md) using https://github.com/phawitb/th-voice-lab.git and its `scripts/setup.py`. Do not download a different model.
2. Run `… voices` and resolve the user's requested voice by exact ID or name. If unspecified, use `thai-01` (public sample). Personal references present on an existing machine are not part of the distributed CC0 set; do not infer their commercial-use permission.
3. Generate using the exact requested text and a new output filename:

```sh
python3 <skill-dir>/scripts/voice_lab.py generate --voice thai-01 --text 'ยินดีต้อนรับเข้าสู่ thai voice lab สร้างเสียงได้ฟรี ไม่จำกัด บนคอมพิวเตอร์เราเอง' --output /absolute/path/welcome.wav
```

Use `--text-file /path/script.txt` for text containing shell metacharacters or multiple lines. Use `--reference /path/voice.wav` instead of `--voice` for a user-provided recording. Speed defaults to 1.0; balanced quality is 12 steps. See `generate --help` for options. Do not invent vocal qualities for numbered reference samples.

4. Wait for `completed`, validate the returned WAV path, and give the user a playable file/link. Report actual duration and any failure. Do not call a queued job complete.

## Recovery and boundaries

- Generation writes `<output-stem>.job.json` immediately after acceptance. If waiting times out (exit 2), resume the same job with `wait --job ID --output /path/file.wav`; never create another job just because polling stopped.
- A receipt with status `submitting` and no job ID means submission was interrupted or uncertain. Reconcile text/voice/time against history before retrying. A stale `.submit.lock` after a killed process must also be checked before removal.
- An uncertain POST is not retried. Read `history`/`voices` to reconcile it first. A full queue should be allowed to drain, not bypassed by starting another model/server.
- Existing outputs/receipts are protected. Use a new filename unless the user authorized replacement; `--overwrite` is explicit.
- Input: 1–2,000 characters per job; audio reference 3–30 seconds and ≤20 MB, first 12 seconds used. For longer scripts, split at natural sentence boundaries into separate named WAVs and preserve text order. Do not silently truncate.
- Runtime generation is local. Installation of dependencies/model on a new machine may need internet. This skill needs a local Codex or Claude Code session with filesystem/terminal access; a remote chat cannot reach the user's localhost.
- Model commercial licensing and reference-voice rights are separate. The eight public samples are labeled CC0; personal/publicity rights are not granted by CC0. Use authorized references and identify synthetic audio appropriately.

For installation and copyable user prompts, read [installation.md](references/installation.md). For API details and troubleshooting, read [api.md](references/api.md).
