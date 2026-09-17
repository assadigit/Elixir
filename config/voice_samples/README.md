# Voice Samples Cache

This folder stores cached TTS preview samples. When you click "Play sample"
in Settings → TTS → Preview, the app generates a short WAV here (named
`<voice_id>.wav`) and plays it in-app. Subsequent previews of the same voice
play instantly from this cache.

## Files
- `af_heart.wav` — Kokoro English voice "af_heart"
- `am_michael.wav` — Kokoro English voice "am_michael"
- `fa_IR-amir-medium.wav` — Piper Persian voice "amir"
- ... (one file per voice, generated on first preview)

## Management
- Use the "Regenerate" button in Settings → TTS → Preview to refresh a sample
- Samples are small (~100-300 KB each)
- Safe to delete — they'll be regenerated on next preview
