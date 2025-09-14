import os
import subprocess
import tempfile
from typing import Optional
import re
import textwrap


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
    playback_speed: float = 1.0,
    captions_text: Optional[str] = None,
    burn_captions: bool = True,
    captions_max_chars_per_line: int = 42,
    captions_max_lines: int = 2,
    ass_captions_text: Optional[str] = None,
    ass_words_per_chunk: int = 6,
    ass_font_name: str = "Arial",
    ass_font_size: int = 64,
    ass_outline: int = 4,
    ass_shadow: int = 2,
    ass_primary_color: str = "&H00FFFFFF&",
    ass_outline_color: str = "&H00454545&",
    ass_back_color: str = "&H00FFFFFF&",
    ass_bold: bool = True,
    ass_italic: bool = False,
    ass_alignment: int = 5,
    ass_margin_v: int = 60,
    ass_events: Optional[list[dict]] = None,
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
        srt_path = os.path.join(tmpdir, "captions.srt") if captions_text else None
        ass_path = os.path.join(tmpdir, "captions.ass") if (ass_captions_text or ass_events) else None

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

        # 3.5) (optional) Build captions SRT aligned proportionally to speech duration
        if captions_text and srt_path:
            _write_proportional_srt(
                captions_text,
                total_seconds=trim_seconds,
                srt_path=srt_path,
                max_chars_per_line=captions_max_chars_per_line,
                max_lines=captions_max_lines,
            )
        # 3.6) (optional) Build ASS captions with centered style and 6-word chunks
        if ass_events and ass_path:
            _write_centered_ass_events(
                ass_events,
                ass_path=ass_path,
                font_name=ass_font_name,
                font_size=ass_font_size,
                outline=ass_outline,
                shadow=ass_shadow,
                primary_color=ass_primary_color,
                outline_color=ass_outline_color,
                back_color=ass_back_color,
                bold=ass_bold,
                italic=ass_italic,
                alignment=ass_alignment,
                margin_v=ass_margin_v,
            )
        elif ass_captions_text and ass_path:
            _write_centered_ass(
                ass_captions_text,
                total_seconds=trim_seconds,
                ass_path=ass_path,
                words_per_chunk=ass_words_per_chunk,
                font_name=ass_font_name,
                font_size=ass_font_size,
                outline=ass_outline,
                shadow=ass_shadow,
                primary_color=ass_primary_color,
                outline_color=ass_outline_color,
                back_color=ass_back_color,
                bold=ass_bold,
                italic=ass_italic,
                alignment=ass_alignment,
                margin_v=ass_margin_v,
            )

        # 4) Mux trimmed video with mixed audio; if captions, burn in via subtitles filter (requires re-encode)
        if (ass_events or ass_captions_text) and burn_captions and ass_path:
            vf_arg = (
                f"subtitles='{ass_path}'"
                if playback_speed == 1.0
                else f"subtitles='{ass_path}',setpts=PTS/{playback_speed}"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                trimmed_video_path,
                "-i",
                mixed_audio_path,
                "-vf",
                vf_arg,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                video_preset,
                "-crf",
                str(video_crf),
            ]
            if playback_speed != 1.0:
                cmd += ["-filter:a", f"atempo={playback_speed}"]
            cmd += [
                "-c:a",
                "aac",
                "-shortest",
                output_video_path,
            ]
            _run_command(cmd)
        elif captions_text and burn_captions and srt_path:
            vf_arg = (
                f"subtitles='{srt_path}'"
                if playback_speed == 1.0
                else f"subtitles='{srt_path}',setpts=PTS/{playback_speed}"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                trimmed_video_path,
                "-i",
                mixed_audio_path,
                "-vf",
                vf_arg,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                video_preset,
                "-crf",
                str(video_crf),
            ]
            if playback_speed != 1.0:
                cmd += ["-filter:a", f"atempo={playback_speed}"]
            cmd += [
                "-c:a",
                "aac",
                "-shortest",
                output_video_path,
            ]
            _run_command(cmd)
        else:
            if playback_speed == 1.0:
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
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    trimmed_video_path,
                    "-i",
                    mixed_audio_path,
                    "-vf",
                    f"setpts=PTS/{playback_speed}",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    video_preset,
                    "-crf",
                    str(video_crf),
                ]
                cmd += ["-filter:a", f"atempo={playback_speed}"]
                cmd += [
                    "-c:a",
                    "aac",
                    "-shortest",
                    output_video_path,
                ]
                _run_command(cmd)

    return output_video_path


def _write_centered_ass(
    text: str,
    *,
    total_seconds: float,
    ass_path: str,
    words_per_chunk: int = 6,
    font_name: str = "Arial",
    font_size: int = 64,
    outline: int = 4,
    shadow: int = 2,
    primary_color: str = "&H00FFFFFF&",
    outline_color: str = "&H00000000&",
    back_color: str = "&H00FFFFFF&",
    bold: bool = True,
    italic: bool = False,
    alignment: int = 5,
    margin_v: int = 60,
) -> None:
    words = _tokenize_words(text)
    if not words:
        words = [text.strip()]
    total_words = len(words)
    if total_words == 0:
        total_words = 1

    def fmt(ts: float) -> str:
        # ASS uses H:MM:SS.cc (centiseconds)
        cs = int(round(ts * 100))
        h = cs // 360000
        cs -= h * 360000
        m = cs // 6000
        cs -= m * 6000
        s = cs // 100
        cs -= s * 100
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # Header and style
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "Collisions: Normal",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{primary_color},&H000000FF&,{outline_color},{back_color},{1 if bold else 0},{1 if italic else 0},0,0,100,100,0,0,1,{outline},{shadow},{alignment},60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    # Build dialogues by grouping words_per_chunk words with proportional timing
    index = 0
    cursor = 0.0
    lines = []
    while index < len(words):
        chunk = words[index:index + max(1, words_per_chunk)]
        index += len(chunk)
        weight = len(chunk) / float(total_words)
        dur = total_seconds * weight
        start = cursor
        end = min(total_seconds, start + dur)
        cursor = end

        text_payload = _escape_ass_text(" ".join(chunk))
        lines.append(f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0000,0000,0000,,{text_payload}")

    with open(ass_path, "w", encoding="utf-8") as f:
        for line in header:
            f.write(line + "\n")
        for line in lines:
            f.write(line + "\n")


_WORD_RE = re.compile(r"\w+['’]?\w*|[.,!?;:\-–—()\[\]\"“”]+")


def _tokenize_words(text: str) -> list[str]:
    return [m.group(0) for m in _WORD_RE.finditer(text.strip())]


def _escape_ass_text(text: str) -> str:
    # Escape braces used by ASS override codes
    return text.replace("{", "(").replace("}", ")")


def _write_centered_ass_events(
    events: list[dict],
    *,
    ass_path: str,
    font_name: str = "Arial",
    font_size: int = 64,
    outline: int = 4,
    shadow: int = 2,
    primary_color: str = "&H00FFFFFF&",
    outline_color: str = "&H00000000&",
    back_color: str = "&H00FFFFFF&",
    bold: bool = True,
    italic: bool = False,
    alignment: int = 5,
    margin_v: int = 60,
) -> None:
    def fmt(ts: float) -> str:
        cs = int(round(ts * 100))
        h = cs // 360000
        cs -= h * 360000
        m = cs // 6000
        cs -= m * 6000
        s = cs // 100
        cs -= s * 100
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "Collisions: Normal",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{primary_color},&H000000FF&,{outline_color},{back_color},{1 if bold else 0},{1 if italic else 0},0,0,100,100,0,0,1,{outline},{shadow},{alignment},60,60,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    lines: list[str] = []
    for ev in events:
        start = float(ev["start"]) if isinstance(ev["start"], (int, float)) else 0.0
        end = float(ev["end"]) if isinstance(ev["end"], (int, float)) else start
        text_payload = _escape_ass_text(str(ev.get("text", "")).strip())
        lines.append(f"Dialogue: 0,{fmt(start)},{fmt(end)},Default,,0000,0000,0000,,{text_payload}")

    with open(ass_path, "w", encoding="utf-8") as f:
        for line in header:
            f.write(line + "\n")
        for line in lines:
            f.write(line + "\n")

def _write_proportional_srt(
    text: str,
    *,
    total_seconds: float,
    srt_path: str,
    max_chars_per_line: int,
    max_lines: int,
) -> None:
    sentences = _split_into_sentences(text)
    if not sentences:
        sentences = [text.strip()]
    total_chars = sum(len(s) for s in sentences) or 1

    def fmt(ts: float) -> str:
        ms = int(round(ts * 1000))
        h = ms // 3600000
        ms -= h * 3600000
        m = ms // 60000
        ms -= m * 60000
        s = ms // 1000
        ms -= s * 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    cursor = 0.0
    for idx, sentence in enumerate(sentences, start=1):
        weight = len(sentence) / total_chars
        dur = total_seconds * weight
        start = cursor
        end = min(total_seconds, start + dur)
        cursor = end

        wrapped = textwrap.wrap(sentence.strip(), width=max_chars_per_line)
        if not wrapped:
            wrapped = [""]
        if len(wrapped) > max_lines:
            wrapped = wrapped[:max_lines]
        payload = "\n".join(wrapped)

        lines.append(f"{idx}\n{fmt(start)} --> {fmt(end)}\n{payload}\n\n")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    # Merge very short trailing fragments
    merged: list[str] = []
    for part in parts:
        if merged and len(part) < 10:
            merged[-1] = merged[-1] + " " + part
        else:
            merged.append(part)
    return merged

