from faster_whisper import WhisperModel
model = WhisperModel('small', device='cpu', compute_type='int8')
segments, info = model.transcribe('assets/audio/default_bgm.mp3')
for s in segments:
    print(f"[{s.start:.2f} - {s.end:.2f}] {s.text}")
