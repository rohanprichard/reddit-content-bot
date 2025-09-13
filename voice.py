from elevenlabs.client import ElevenLabs
from elevenlabs import save
import uuid

from secret import secrets


elevenlabs = ElevenLabs(
  api_key=secrets.elevenlabs_api_key
)
voice_id_mapping = {
    "deep male british?": "JBFqnCBsd6RMkjVDRZzb",
    "deep american male - clyde": "2EiwWnXFnvU5JabPnv8n",
    "american male whisper - Thomas": "GBv7mTt0atIp3Br8iCZE",
    "female american creepy - Veda": "1rnYMVDXZksVr6x7pZPX",
    "lauden b female whisper american": "O4NKp88bb2JkAnrCbwQt"
}

def generate_audio(text: str, uuid: str):
    audio = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id="O4NKp88bb2JkAnrCbwQt",
        model_id="eleven_v3",
        output_format="mp3_44100_128",
        voice_settings={
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": 1.2
        }
    )

    file_path = f"data/{uuid}/audio.mp3"
    save(audio, file_path)

    return file_path
