# Local API and troubleshooting

Default endpoint: http://127.0.0.1:7860. The client accepts only loopback HTTP URLs; use `--url` before the subcommand to change the port. Credentials and external services are not used.

| Client command | Server operation |
|---|---|
| `status` | GET /api/status |
| `voices` | GET /api/voices (IDs, names, license, audio_url) |
| `upload FILE` | POST /api/upload, multipart field `file`; returns the stored voice ID |
| `generate` | POST /api/generate; accepts text, voice_id, speed, steps, guidance |
| `wait --job ID --output FILE.wav` | Poll GET /api/jobs/ID and download the completed PCM WAV |
| `history` | GET /api/history (latest 100 jobs, newest first) |

A job progresses through queued, loading, generating, processing, completed/failed. One worker serializes inference; at most three active jobs are accepted. First use loads the model into RAM. Do not interpret low progress as a crash. On exit 2, resume using the printed job ID or the adjacent `.job.json` receipt.

HTTP 422: fix text/settings or reference length/format. 429: wait for queue space. 404 on a known job: report missing history and do not claim completion. Model failure: inspect the project's data/server.log or data/skill-server.log; keep the original failure visible. Startup requires the runtime selected by the project's `.runtime.json`/launcher, ffmpeg, and cached openbmb/VoxCPM2. For new customers, run the repository's setup.py to create an isolated environment and download the model; do not pip-install into an unrelated existing environment.

The server output remains in data/outputs; the client copies a validated WAV to the requested destination. A successful download does not prove pronunciation quality. Listen or use an available local transcription check when the task calls for it; state what was actually checked.

Concurrency: an exclusive `.submit.lock` reserves the output while submitting/waiting. The `.job.json` receipt initially records `submitting`, then atomically records `accepted` with job ID. If interrupted before an ID is recorded, reconcile exact text/voice/time against server history; do not assume no job was created. A lock left by a killed process is only removed after checking that process and history.
