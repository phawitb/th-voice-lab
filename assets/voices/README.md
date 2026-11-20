# Public Thai reference voices

Eight distinct Thai speakers from [Common Voice Corpus 17.0, public mirror](https://huggingface.co/datasets/fsicoli/common_voice_17_0). The dataset card declares **CC0 1.0 / Public Domain**. The source card is retained in `sources/dataset-card.md`.

- `manifest.json`: original clip names, transcripts, source/archive URLs, SHA-256 of source MP3s and anonymous speaker fingerprints.
- `thai-01.wav` … `thai-08.wav`: derived mono 24 kHz references, normalized to approximately −20 LUFS with ffmpeg.
- `sources/*.mp3`: selected original CC0 clips, for provenance/reproducibility.

Sample display names are numbers, not real speaker names. No personal Mhee reference, uploaded recordings, outputs, or runtime history are distributed. The app copies these public assets into its ignored `data/` directory on first use; existing local catalogues are preserved.

[CC0 terms](https://creativecommons.org/publicdomain/zero/1.0/) permit commercial reuse of the covered copyright interests. Privacy, publicity and other personal rights are separate. Do not imply the original speakers endorse a product or that synthetic speech is their authentic statement.
