import os
from typing import Optional, List, Dict

import whisper  # openai-whisper


def transcribe_words(
    audio_path: str,
    model_name: str = "base",
    device: str = "cpu",
) -> List[Dict]:
    """
    Run local Whisper and return a flat list of words with start/end timestamps.
    If the model doesn't return word timing, approximate by splitting segments evenly.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(audio_path, word_timestamps=True, verbose=False)

    words: List[Dict] = []
    for seg in result.get("segments", []):
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start))
        seg_text = seg.get("text", "").strip()
        seg_words = seg.get("words")

        if seg_words:
            for w in seg_words:
                wtext = w.get("word", "").strip()
                wstart = float(w.get("start", seg_start))
                wend = float(w.get("end", wstart))
                if wtext:
                    words.append({"text": wtext, "start": wstart, "end": wend})
        else:
            # Fallback: naive split by whitespace across the segment duration
            tokens = [t for t in seg_text.split() if t]
            if not tokens:
                continue
            dur = max(0.0, seg_end - seg_start)
            step = dur / max(1, len(tokens))
            cursor = seg_start
            for tok in tokens:
                start = cursor
                end = min(seg_end, start + step)
                cursor = end
                words.append({"text": tok, "start": start, "end": end})

    return words


def words_to_ass_events(
    words: List[Dict],
    words_per_chunk: int = 6,
) -> List[Dict]:
    """
    Group words into fixed-size chunks, returning ASS dialogue event dicts with start/end/text.
    """
    events: List[Dict] = []
    idx = 0
    while idx < len(words):
        chunk = words[idx: idx + max(1, words_per_chunk)]
        idx += len(chunk)
        if not chunk:
            break
        start = float(chunk[0]["start"])
        end = float(chunk[-1]["end"]) if float(chunk[-1]["end"]) >= start else start
        text = " ".join(w["text"] for w in chunk).strip()
        events.append({"start": start, "end": end, "text": text})
    return events


def words_to_sentence_events(words: List[Dict]) -> List[Dict]:
    """
    Group consecutive words into sentence-level events based on end punctuation (.?!).
    """
    events: List[Dict] = []
    if not words:
        return events

    def is_end_punct(token: str) -> bool:
        return token in {".", "?", "!", ".”", "!”", "?”"}

    current: List[Dict] = []
    for w in words:
        current.append(w)
        token = w["text"].strip()
        if is_end_punct(token):
            start = float(current[0]["start"]) if current else 0.0
            end = float(current[-1]["end"]) if current else start
            text = " ".join(t["text"] for t in current).strip()
            events.append({"start": start, "end": end, "text": text})
            current = []

    if current:
        start = float(current[0]["start"]) if current else 0.0
        end = float(current[-1]["end"]) if current else start
        text = " ".join(t["text"] for t in current).strip()
        events.append({"start": start, "end": end, "text": text})

    return events


def words_to_sentence_chunk_events(
    words: List[Dict],
    max_words_per_event: int = 7,
) -> List[Dict]:
    """
    Group words into sentence-bounded chunks. Sentences end on . ? ! (optionally followed by quotes).
    Within each sentence, split into events of up to max_words_per_event words.
    This guarantees no overlap between the end of one sentence and the start of the next.
    """
    if not words:
        return []

    def is_end_token(tok: str) -> bool:
        t = tok.strip()
        return t in {".", "?", "!", ".”", "!”", "?”", "…"}

    # Partition into sentences
    sentences: List[List[Dict]] = []
    current: List[Dict] = []
    for w in words:
        current.append(w)
        if is_end_token(w["text"]):
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)

    # Chunk each sentence without crossing boundaries
    events: List[Dict] = []
    for sent in sentences:
        idx = 0
        while idx < len(sent):
            chunk = sent[idx: idx + max(1, max_words_per_event)]
            idx += len(chunk)
            start = float(chunk[0]["start"]) if chunk else 0.0
            end = float(chunk[-1]["end"]) if chunk else start
            text = " ".join(x["text"] for x in chunk).strip()
            events.append({"start": start, "end": end, "text": text})

    return events


def words_to_single_word_events(words: List[Dict]) -> List[Dict]:
    """
    One word per event. If a punctuation-only token immediately follows a word,
    merge it into the previous event's text and extend its end time.
    """
    events: List[Dict] = []
    def is_punct(token: str) -> bool:
        t = token.strip()
        return len(t) > 0 and all(c in ".,!?;:-–—()[]\"“”'’" for c in t)

    for w in words:
        token = w.get("text", "").strip()
        if not token:
            continue
        if is_punct(token) and events:
            # append punctuation to previous event
            events[-1]["text"] = (events[-1]["text"] + token)
            # extend end time to this token's end if provided
            try:
                events[-1]["end"] = float(w.get("end", events[-1]["end"]))
            except Exception:
                pass
            continue
        start = float(w.get("start", 0.0))
        end = float(w.get("end", start))
        events.append({"start": start, "end": end, "text": token})

    return events
