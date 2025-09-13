### Compose a video from narration, long background video, and music

Requires `ffmpeg` and `ffprobe` on PATH.

```python
from media import compose_video_with_speech

output = compose_video_with_speech(
    speech_audio_path="data/audio-<uuid>.mp3",
    background_video_path="data/bg.mp4",
    background_music_path="data/music.mp3",
    output_video_path="data/final-<uuid>.mp4",
    music_volume_db_reduction=8.0,   # gentler reduction
    enable_ducking=True,             # auto-duck music under speech
)
print("Wrote:", output)
```

Notes:
- The background video and music are trimmed to the speech duration.
- The music is attenuated by `music_volume_db_reduction` dB before a 2-track `amix`.
- Video is re-encoded on the trim step for accurate cutting (x264 CRF/preset configurable).
- Final mux copies the trimmed video stream to avoid a second generation loss.


