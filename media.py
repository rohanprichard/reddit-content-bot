import os
import subprocess
import tempfile
from typing import Optional


def _run_command(args: list[str]) -> None:
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\nSTDERR:\n{process.stderr.decode('utf-8', errors='ignore')}")


def _probe_duration_seconds(path: str) -> float:
    args = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {process.stderr.decode('utf-8', errors='ignore')}")
    try:
        return float(process.stdout.decode("utf-8").strip())
    except ValueError as exc:
        raise RuntimeError(f"Unable to parse duration from ffprobe output for {path}") from exc


def compose_video_with_speech(
    speech_audio_path: str,
    background_video_path: str,
    background_music_path: str,
    output_video_path: str,
    *,
    music_volume_db_reduction: float = 8.0,
    video_crf: int = 18,
    video_preset: str = "veryfast",
    enable_ducking: bool = True,
    ducking_threshold: float = 0.05,
    ducking_ratio: float = 4.0,
    ducking_attack_ms: int = 15,
    ducking_release_ms: int = 300,
    speech_mix_weight: float = 1.0,
    music_mix_weight: float = 1.0,
) -> str:
    """
    Create a video matching the speech duration by trimming a long background video and music,
    then mixing speech over the music and muxing with the trimmed video.

    Args:
        speech_audio_path: Path to the narration/speech audio file (duration source).
        background_video_path: Path to a longer video file to be trimmed.
        background_music_path: Path to a longer music file to be trimmed and mixed under speech.
        output_video_path: Path where the final composed video will be written (e.g. ".mp4").
        music_volume_db_reduction: How much to lower music level before mixing (in dB).
        video_crf: x264 CRF quality (lower is higher quality, typical 18-23).
        video_preset: x264 preset for encoding speed/efficiency.

    Returns:
        The output path provided (for convenience).

    Requires:
        ffmpeg and ffprobe available on PATH.
    """

    if not os.path.exists(speech_audio_path):
        raise FileNotFoundError(f"Speech audio not found: {speech_audio_path}")
    if not os.path.exists(background_video_path):
        raise FileNotFoundError(f"Background video not found: {background_video_path}")
    if not os.path.exists(background_music_path):
        raise FileNotFoundError(f"Background music not found: {background_music_path}")

    speech_duration = _probe_duration_seconds(speech_audio_path)
    trim_seconds = max(0.0, speech_duration)
    trim_arg = f"{trim_seconds:.3f}"

    with tempfile.TemporaryDirectory() as tmpdir:
        trimmed_video_path = os.path.join(tmpdir, "video_trim.mp4")
        trimmed_music_path = os.path.join(tmpdir, "music_trim.m4a")
        mixed_audio_path = os.path.join(tmpdir, "mixed_audio.m4a")

        # 1) Trim video to speech duration (re-encode to ensure accurate cut boundaries)
        _run_command([
            "ffmpeg",
            "-y",
            "-ss",
            "0",
            "-t",
            trim_arg,
            "-i",
            background_video_path,
            "-c:v",
            "libx264",
            "-preset",
            video_preset,
            "-crf",
            str(video_crf),
            "-an",
            trimmed_video_path,
        ])

        # 2) Trim music to speech duration and lower its volume pre-mix
        _run_command([
            "ffmpeg",
            "-y",
            "-ss",
            "0",
            "-t",
            trim_arg,
            "-i",
            background_music_path,
            "-af",
            f"volume=-{float(music_volume_db_reduction)}dB",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            trimmed_music_path,
        ])

        # 3) Mix speech and (attenuated) music
        #    Optional: apply sidechain compression (ducking) so music dips under speech but stays audible between phrases.
        if enable_ducking:
            filter_complex = (
                f"[1:a][0:a]sidechaincompress=threshold={ducking_threshold}:ratio={ducking_ratio}:"
                f"attack={ducking_attack_ms}:release={ducking_release_ms}[duck];"
                f"[0:a][duck]amix=inputs=2:weights={speech_mix_weight} {music_mix_weight}:duration=first:dropout_transition=3[a]"
            )
        else:
            filter_complex = (
                f"[0:a][1:a]amix=inputs=2:weights={speech_mix_weight} {music_mix_weight}:duration=first:dropout_transition=3[a]"
            )

        _run_command([
            "ffmpeg",
            "-y",
            "-i",
            speech_audio_path,
            "-i",
            trimmed_music_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            mixed_audio_path,
        ])

        # 4) Mux trimmed video with mixed audio
        _run_command([
            "ffmpeg",
            "-y",
            "-i",
            trimmed_video_path,
            "-i",
            mixed_audio_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            output_video_path,
        ])

    return output_video_path


