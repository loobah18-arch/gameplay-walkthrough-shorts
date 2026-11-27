"""
AniDoc-Style ASS Subtitle & Kinetic Karaoke Builder.
Replicates the signature AniDoc main branch subtitle engine:
- Double-layer bloom glow (Layer 0: 18px blur glow, Layer 1: 4px crisp text)
- Word-by-word kinetic karaoke (spoken words in white, upcoming words dimmed)
- Vibrant rotating neon accent palette (#FF3B5C, #3DFF7A, #B266FF, #33D6FF, #FFC533)
- Pop-in micro-animation (\fscx106\fscy106\t(0,90,\fscx100\fscy100))
- Dynamic 2-row auto-wrap fitting with safe frame margin control
- Frame-accurate Whisper audio transcription on sliced cutscene audio
"""
import html
import json
import os
import re
import subprocess
from typing import List, Dict, Any, Optional
from config.settings import SUBTITLE_STYLE, DRAMATIC_KEYWORDS, ASPECT_RATIOS

ANIDOC_COLORS = ["#FF3B5C", "#3DFF7A", "#B266FF", "#33D6FF", "#FFC533"]
ANIDOC_FONT = "Montserrat ExtraBold"
ANIDOC_DIM = "&H00A0A0A0&"


def ass_col(hexc: str, a: str = "00") -> str:
    """Converts #RRGGBB hex string to ASS &HAABBGGRR& color format."""
    cleaned = hexc.lstrip("#")
    if len(cleaned) != 6:
        return f"&H{a}FFFFFF&"
    r, g, b = cleaned[0:2], cleaned[2:4], cleaned[4:6]
    return f"&H{a}{b}{g}{r}&"


def clean_token(t: str) -> str:
    """Normalizes and uppercases word token for clean social short typography."""
    return re.sub(r"[^\w'?!.,-]", "", t).upper()


class SubtitleBuilder:
    """Builds AniDoc-grade styled ASS subtitle files from audio words or cue lists."""

    @staticmethod
    def format_ass_time(seconds: float) -> str:
        """Converts float seconds into ASS timestamp format: H:MM:SS.cc"""
        total_cs = int(round(max(0.0, float(seconds)) * 100))
        h, rem = divmod(total_cs, 360000)
        m, rem = divmod(rem, 6000)
        s, cs = divmod(rem, 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        """Escapes braces and normalizes line breaks for safe ASS Dialogue lines."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        normalized = normalized.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        return normalized.replace("\n", "\\N")

    @classmethod
    def highlight_text(cls, text: str, keywords: List[str] = DRAMATIC_KEYWORDS) -> str:
        """
        Wraps matched emotional/dramatic words or multi-word phrases in ASS color tags.
        Preserves Bold=1 styling.
        """
        safe_text = cls._escape_ass_text(text)
        if not safe_text or not keywords:
            return safe_text

        highlight_color = SUBTITLE_STYLE.get("highlight_color", "&H003B5CFF&")
        primary_color = SUBTITLE_STYLE.get("primary_color", "&H00FFFFFF&")

        cleaned_kws = sorted({k.strip() for k in keywords if k and k.strip()}, key=len, reverse=True)
        if not cleaned_kws:
            return safe_text

        pattern = re.compile(
            r"(?<!\w)(" + "|".join(re.escape(k) for k in cleaned_kws) + r")(?!\w)",
            re.IGNORECASE,
        )

        parts = safe_text.split("\\N")
        highlighted_parts = []
        for part in parts:
            highlighted_parts.append(
                pattern.sub(
                    lambda m: f"{{\\c{highlight_color}\\b1}}{m.group(0)}{{\\c{primary_color}\\b1}}",
                    part,
                )
            )
        return "\\N".join(highlighted_parts)

    @classmethod
    def format_header_question(cls, question: str) -> str:
        """
        Formats clear, engaging question hooks for the top safe-zone black bar.
        """
        cleaned = cls._escape_ass_text(question).strip().upper()
        if "|" in cleaned:
            parts = cleaned.split("|", 1)
            cleaned = parts[1].strip() if ("?" in parts[1] or len(parts[1].strip()) > 5) else parts[0].strip()

        hl = SUBTITLE_STYLE.get("accent_color", "&H002020FF&")
        white = "&H00FFFFFF&"

        keywords = [
            "DESERVE", "ENDING", "1V1", "BEAT", "COLDEST", "SURVIVE",
            "KILL", "CHOICE", "BETRAYAL", "VILLAIN", "REDEMPTION",
            "DEVIANT", "SACRIFICE", "MACHINE", "TRUTH", "CANON",
            "MONSTER", "EVIL", "WRONG", "RIGHT", "FORGIVE", "DEAD"
        ]

        pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.IGNORECASE)
        if pattern.search(cleaned):
            styled = pattern.sub(lambda m: f"{{\\c{hl}\\b1}}{m.group(0)}{{\\c{white}\\b1}}", cleaned)
            return f"{{\\b1\\c{white}}}{styled}"

        words = cleaned.split()
        if len(words) > 3:
            lead = " ".join(words[:-2])
            tail = " ".join(words[-2:])
            return f"{{\\b1\\c{white}}}{lead} {{\\c{hl}\\b1}}{tail}"

        return f"{{\\b1\\c{white}}}{cleaned}"

    @classmethod
    def transcribe_audio_words(
        cls,
        media_path: str,
        temp_dir: str = "temp",
    ) -> List[Dict[str, Any]]:
        """
        Transcribes the sliced cutscene audio directly using Whisper for exact word-level timing.
        Eliminates YouTube VTT time-drift, delay, and rolling repetition.
        Returns: [{"w": "WORD", "s": 0.50, "e": 0.85}, ...]
        """
        if not os.path.isfile(media_path):
            return []

        os.makedirs(temp_dir, exist_ok=True)
        wav_path = os.path.join(temp_dir, f"audio_{os.path.basename(media_path)}.wav")

        # 1. Extract 16kHz mono audio slice
        try:
            cmd = [
                "ffmpeg", "-nostdin", "-v", "error", "-y",
                "-i", media_path,
                "-vn", "-ac", "1", "-ar", "16000",
                wav_path,
            ]
            subprocess.run(cmd, check=True)
        except Exception as ex:
            print(f"⚠️ [transcribe_audio_words] FFmpeg audio extraction failed: {ex}")
            return []

        # 2. Try Groq Whisper API first if API key is configured (lightning fast: ~0.3s)
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            try:
                import urllib.request
                import json
                print("⚡ Transcribing audio with Groq Whisper Large-v3 (word timestamps)...")
                # Check file size (Groq limit is 25MB, 50s 16kHz mono wav is only ~1.6MB)
                with open(wav_path, "rb") as af:
                    audio_bytes = af.read()

                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                body = bytearray()
                # model
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3\r\n".encode())
                # response_format
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\nverbose_json\r\n".encode())
                # timestamp_granularities[]
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"timestamp_granularities[]\"\r\n\r\nword\r\n".encode())
                # file
                body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
                body.extend(audio_bytes)
                body.extend(f"\r\n--{boundary}--\r\n".encode())

                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    data=bytes(body),
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    raw_words = data.get("words", [])
                    out_words = []
                    for rw in raw_words:
                        cleaned = clean_token(rw.get("word", ""))
                        if cleaned:
                            out_words.append({
                                "w": cleaned,
                                "s": round(float(rw.get("start", 0.0)), 2),
                                "e": round(float(rw.get("end", 0.0)), 2),
                            })
                    if out_words:
                        print(f"✅ Groq Whisper transcribed {len(out_words)} words.")
                        return out_words
            except Exception as e_groq:
                print(f"⚠️ Groq transcription fallback: {e_groq}")

        # 3. Fallback to local faster-whisper (CPU int8 'small' model)
        try:
            from faster_whisper import WhisperModel
            whisper_model_name = os.environ.get("WHISPER_MODEL", "small")
            print(f"🎙️ Transcribing audio locally with faster-whisper ('{whisper_model_name}')...")
            model = WhisperModel(whisper_model_name, device="cpu", compute_type="int8")
            segs, _ = model.transcribe(wav_path, beam_size=1, word_timestamps=True, vad_filter=True)
            words = []
            for seg in segs:
                if getattr(seg, "words", None):
                    for w in seg.words:
                        cleaned = clean_token(w.word)
                        if cleaned:
                            words.append({
                                "w": cleaned,
                                "s": round(float(w.start), 2),
                                "e": round(float(w.end), 2),
                            })
            if words:
                print(f"✅ faster-whisper transcribed {len(words)} frame-accurate words.")
                return words
        except ImportError:
            print("ℹ️ faster-whisper not installed; using transcript cue fallback.")
        except Exception as e_whisper:
            print(f"⚠️ faster-whisper transcription error: {e_whisper}")
        finally:
            if os.path.isfile(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

        return []

    @classmethod
    def cues_to_words(
        cls,
        cues: List[Dict[str, Any]],
        time_offset: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Converts coarse VTT cues into estimated word-level timestamps when Whisper is unavailable.
        """
        words = []
        for cue in cues:
            if cue.get("end", 0.0) <= time_offset:
                continue
            rel_start = max(0.0, cue["start"] - time_offset)
            rel_end = max(rel_start + 0.1, cue["end"] - time_offset)
            dur = rel_end - rel_start

            raw_tokens = [clean_token(t) for t in cue.get("text", "").split()]
            raw_tokens = [t for t in raw_tokens if t]
            if not raw_tokens:
                continue

            per_word = dur / len(raw_tokens)
            for i, tok in enumerate(raw_tokens):
                ws = rel_start + (i * per_word)
                we = ws + per_word
                words.append({
                    "w": tok,
                    "s": round(ws, 2),
                    "e": round(we, 2),
                })
        return words

    @classmethod
    def generate_anidoc_ass(
        cls,
        words: List[Dict[str, Any]],
        output_path: str,
        aspect_ratio_key: str = "vertical_letterbox",
        max_duration: Optional[float] = None,
        top_question: Optional[str] = None,
    ) -> str:
        """
        Generates production-grade AniDoc ASS subtitles:
        - Layer 0: Gaussian blurred atmospheric bloom glow (18px border, blur 16)
        - Layer 1: Crisp high-contrast text with colored outline and shadow
        - Spoken words bright white, remaining words dimmed
        - Dynamic 2-row wrapping with character width constraints
        """
        if aspect_ratio_key not in ASPECT_RATIOS:
            aspect_ratio_key = "square"

        preset = ASPECT_RATIOS[aspect_ratio_key]
        w_res = preset["play_res_x"]
        h_res = preset["play_res_y"]

        # Y position of the subtitle text
        if aspect_ratio_key == "vertical_letterbox":
            # 16:9 video is centered in y=656 to 1264.
            # int(H * 0.53) = 1017px, placed in the lower half of the widescreen video.
            y_pos = int(h_res * 0.53)
            header_margin_v = 280
            header_font_size = 52
        elif aspect_ratio_key == "square_letterbox":
            y_pos = int(h_res * 0.53)
            header_margin_v = 180
            header_font_size = 48
        elif "square" in aspect_ratio_key:
            y_pos = int(h_res * 0.72)
            header_margin_v = 45
            header_font_size = 36
        else:
            y_pos = int(h_res * 0.53)
            header_margin_v = 140
            header_font_size = 44

        header = f"""[Script Info]
Title: AniDoc Autonomous Gameplay Short Subtitles
ScriptType: v4.00+
PlayResX: {w_res}
PlayResY: {h_res}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{ANIDOC_FONT},98,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H96000000,1,0,0,0,100,100,3,0,1,0,3,5,60,60,0,1
Style: HeaderQuestion,{ANIDOC_FONT},{header_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0.8,0,1,0,0,8,60,60,{header_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        clip_end_sec = max_duration if max_duration is not None else 58.0
        if top_question and top_question.strip():
            styled_q = cls.format_header_question(top_question)
            end_q_str = cls.format_ass_time(clip_end_sec)
            events.append(f"Dialogue: 1,0:00:00.00,{end_q_str},HeaderQuestion,,0,0,0,,{styled_q}")

        # Filter words within duration
        valid_words = [
            w for w in words
            if w.get("w") and (max_duration is None or w["s"] < max_duration)
        ]

        if not valid_words:
            full_content = header + "\n".join(events) + "\n"
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            return output_path

        # Chunk into bursts (AniDoc chunking rules: max 4 words, max 18 chars, pause > 0.5s)
        lines = []
        cur = []
        for w in valid_words:
            if cur and (
                len(cur) >= 4
                or sum(len(x["w"]) for x in cur) >= 18
                or (w["s"] - cur[-1]["e"]) > 0.5
                or (cur[-1]["w"][-1:] in ".?!," and len(cur) >= 2)
            ):
                lines.append(cur)
                cur = []
            cur.append(w)
        if cur:
            lines.append(cur)

        # Build events for each burst
        for li, ln in enumerate(lines):
            # Rotate vibrant accent color by line
            col = ANIDOC_COLORS[li % len(ANIDOC_COLORS)]
            ass_accent = ass_col(col)

            t_end = min(
                ln[-1]["e"] + 0.35,
                lines[li + 1][0]["s"] if li + 1 < len(lines) else clip_end_sec
            )
            if max_duration is not None:
                t_end = min(t_end, max_duration)

            toks = [clean_token(w["w"]) for w in ln]
            toks = [t for t in toks if t]
            if not toks:
                continue

            # Row splitting and width budgeting (AniDoc ~13-14 chars per row)
            ROWC = int(os.environ.get("CAP_ROW_CHARS", 13))
            def _w(r):
                return sum(len(t) for t in r) + max(0, len(r) - 1)

            if _w(toks) <= ROWC or len(toks) == 1:
                rows_ = [toks]
            else:
                rows_ = min(
                    ([toks[:i], toks[i:]] for i in range(1, len(toks))),
                    key=lambda rr: max(_w(rr[0]), _w(rr[1])),
                )
            widest = max(_w(r) for r in rows_)
            fs_tag = f"\\fs{max(56, int(98 * ROWC / widest))}" if widest > ROWC else ""

            ends = set()
            n_ = 0
            for r in rows_[:-1]:
                n_ += len(r)
                ends.add(n_ - 1)

            for k in range(len(toks)):
                a = ln[min(k, len(ln) - 1)]["s"]
                b = ln[k + 1]["s"] if k + 1 < len(toks) and k + 1 < len(ln) else t_end
                if b <= a:
                    continue

                parts = []
                for m, t in enumerate(toks):
                    # Spoken word is bright white; future words are dim
                    color_tag = "{\\1c&H00FFFFFF&}" if m <= k else f"{{\\1c{ANIDOC_DIM}}}"
                    parts.append(color_tag + t)
                    if m in ends:
                        parts.append("\\N")
                    elif m != len(toks) - 1:
                        parts.append(" ")

                txt = "".join(parts).replace(" \\N", "\\N")
                pop = "{\\fscx106\\fscy106\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
                glow = f"{{\\pos({w_res // 2},{y_pos}){fs_tag}\\bord18\\blur16\\3c{ass_accent}\\3a&H20&\\shad0\\1a&HFF&}}"
                main = f"{{\\pos({w_res // 2},{y_pos}){fs_tag}\\bord4\\blur3\\3c{ass_accent}\\shad3}}"

                start_str = cls.format_ass_time(a)
                end_str = cls.format_ass_time(b)
                events.append(f"Dialogue: 0,{start_str},{end_str},Cap,,0,0,0,,{glow}{pop}{txt}")
                events.append(f"Dialogue: 1,{start_str},{end_str},Cap,,0,0,0,,{main}{pop}{txt}")

        full_content = header + "\n".join(events) + "\n"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return output_path

    @classmethod
    def generate_ass(
        cls,
        cues: List[Dict[str, Any]],
        output_path: str,
        aspect_ratio_key: str = "square",
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
        top_question: Optional[str] = None,
    ) -> str:
        """
        Legacy/line-level ASS generator with keyword highlights and header question.
        Maintains backward compatibility with legacy test suite.
        """
        if aspect_ratio_key not in ASPECT_RATIOS:
            aspect_ratio_key = "square"

        preset = ASPECT_RATIOS[aspect_ratio_key]
        res_x = preset["play_res_x"]
        res_y = preset["play_res_y"]

        is_square = "square" in aspect_ratio_key
        font_size = (
            SUBTITLE_STYLE["font_size_square"]
            if is_square
            else SUBTITLE_STYLE["font_size_vertical"]
        )
        margin_v = (
            SUBTITLE_STYLE["margin_v_square"]
            if is_square
            else SUBTITLE_STYLE["margin_v_vertical"]
        )

        if aspect_ratio_key == "vertical_letterbox":
            header_font_size = 52
            header_margin_v = 280
        elif aspect_ratio_key == "square_letterbox":
            header_font_size = 48
            header_margin_v = 180
        elif is_square:
            header_font_size = 36
            header_margin_v = 45
        else:
            header_font_size = 44
            header_margin_v = 140

        header = f"""[Script Info]
Title: Cinematic Walkthrough Short Subtitles
ScriptType: v4.00+
WrapStyle: 1
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CinematicDefault,{SUBTITLE_STYLE['font_name']},{font_size},{SUBTITLE_STYLE['primary_color']},&H000000FF,{SUBTITLE_STYLE['outline_color']},{SUBTITLE_STYLE['outline_color']},1,0,0,0,100,100,0.5,0,1,{SUBTITLE_STYLE['outline_width']},{SUBTITLE_STYLE['shadow_depth']},2,40,40,{margin_v},1
Style: HeaderQuestion,{SUBTITLE_STYLE['font_name']},{header_font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0.8,0,1,0,0,8,60,60,{header_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        clip_end_sec = max_duration if max_duration is not None else 58.0
        if top_question and top_question.strip():
            styled_q = cls.format_header_question(top_question)
            end_q_str = cls.format_ass_time(clip_end_sec)
            events.append(f"Dialogue: 1,0:00:00.00,{end_q_str},HeaderQuestion,,0,0,0,,{styled_q}")

        for cue in cues:
            rel_start = cue["start"] - time_offset
            rel_end = cue["end"] - time_offset

            if rel_end <= 0.0:
                continue
            if max_duration is not None and rel_start >= max_duration:
                continue

            start_sec = max(0.0, rel_start)
            end_sec = rel_end if max_duration is None else min(rel_end, max_duration)
            if end_sec <= start_sec:
                end_sec = start_sec + 0.5
                if max_duration is not None:
                    end_sec = min(end_sec, max_duration)

            start_str = cls.format_ass_time(start_sec)
            end_str = cls.format_ass_time(end_sec)
            styled_text = cls.highlight_text(cue["text"])
            if not styled_text:
                continue

            events.append(f"Dialogue: 0,{start_str},{end_str},CinematicDefault,,0,0,0,,{styled_text}")

        full_content = header + "\n".join(events) + "\n"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return output_path
