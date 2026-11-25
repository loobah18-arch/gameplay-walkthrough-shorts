"""
Configuration settings for Gameplay Walkthrough Shorts Clipper.
"""
import os
from typing import Dict, Any

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Default GitHub Repo & Action Workflow for Cloud Dispatch
DEFAULT_GITHUB_REPO = "loobah18-arch/gameplay-walkthrough-shorts"
DEFAULT_WORKFLOW_FILE = "render_walkthrough_short.yml"

# Aspect Ratio Presets
# Reference style (https://youtube.com/shorts/xoJydV-xKVw) uses 9:16 vertical canvas
# with cutscene centered and pure black bars on top and bottom for engaging questions.
ASPECT_RATIOS: Dict[str, Dict[str, Any]] = {
    "vertical_letterbox": {
        "name": "9:16 Vertical Letterbox (Black Bars, Reference Style xoJydV-xKVw)",
        "width": 1080,
        "height": 1920,
        "play_res_x": 1080,
        "play_res_y": 1920,
        "description": "16:9 cutscene centered with pure black bars on top & bottom. Header question on top black space.",
    },
    "square_letterbox": {
        "name": "9:16 Square in Vertical Letterbox (1:1 Square + Black Bars)",
        "width": 1080,
        "height": 1920,
        "play_res_x": 1080,
        "play_res_y": 1920,
        "description": "1:1 square cutscene centered with pure black bars on top & bottom. Header question on top black space.",
    },
    "square": {
        "name": "1:1 Square (Cinematic Cutscene Reference Style)",
        "width": 1080,
        "height": 1080,
        "play_res_x": 1080,
        "play_res_y": 1080,
        "description": "True 1:1 square crop centered on cinematic cutscenes and characters.",
    },
    "square_hd": {
        "name": "1:1 Ultra-HD (2160x2160)",
        "width": 2160,
        "height": 2160,
        "play_res_x": 2160,
        "play_res_y": 2160,
        "description": "4K native 1:1 square master render.",
    },
    "vertical_crop": {
        "name": "9:16 Vertical Center-Crop",
        "width": 1080,
        "height": 1920,
        "play_res_x": 1080,
        "play_res_y": 1920,
        "description": "Full vertical 9:16 center cropped on focal action.",
    },
    "vertical_blurred": {
        "name": "9:16 Vertical Blurred Background",
        "width": 1080,
        "height": 1920,
        "play_res_x": 1080,
        "play_res_y": 1920,
        "description": "16:9 gameplay centered with blurred game background padding.",
    },
}

DEFAULT_ASPECT_RATIO = "vertical_letterbox"

# Subtitle Styling Constants (ASS Format)
SUBTITLE_STYLE = {
    "font_name": "Montserrat",
    "fallback_font": "DejaVu Sans",
    "font_size_square": 46,
    "font_size_vertical": 54,
    "primary_color": "&H00FFFFFF&",    # Crisp white text
    "highlight_color": "&H0000D4FF&",  # Warm golden amber / yellow for active keywords
    "accent_color": "&H002020FF&",     # Vibrant crimson red for debate question keywords (xoJydV-xKVw style)
    "outline_color": "&H00000000&",    # Solid black outline
    "outline_width": 3.5,
    "shadow_depth": 1.5,
    "margin_v_square": 110,            # Vertical margin from bottom
    "margin_v_vertical": 240,
}

# Audio Normalization Parameters (EBU R128 YouTube standard)
AUDIO_NORM_SETTINGS = {
    "integrated_lufs": -14.0,
    "true_peak": -1.5,
    "loudness_range": 7.0,
}

# Color Enhancements for Gameplay Cutscenes
VIDEO_FILTER_ENHANCE = (
    "unsharp=3:3:0.6:3:3:0.0,"
    "eq=contrast=1.06:saturation=1.12:brightness=0.01"
)

# Cutscene Emotion Detection Keywords (High-Tension Dialogue)
DRAMATIC_KEYWORDS = [
    # Philosophical & existential (Detroit, Cyberpunk)
    "machine", "living being", "alive", "human", "feel", "fear", "death", "die",
    "soul", "conscious", "deviant", "obey", "order", "choice", "free",
    # Confrontation & moral dilemmas
    "betray", "truth", "lie", "kill", "save", "sacrifice", "monster", "guilty",
    "innocent", "trust", "forgive", "revenge", "protect", "promise", "regret",
    # Dramatic exclamations & intensity
    "stop", "wait", "look at me", "why did you", "don't do this", "it's over",
    "never again", "who are you", "what have you done",
]

# Payoff Detection & Narrative Arc Keywords
PAYOFF_KEYWORDS: Dict[str, list] = {
    "mic_drop": [
        "that is my purpose", "just a machine", "not a living being", "it's over",
        "never again", "whatever you want me to be", "wake up", "goodbye",
        "you lose", "i win", "too late", "game over", "now you know",
        "i don't care", "nothing personal", "my choice", "i am free",
        "i'm alive", "we are alive", "not this time",
        "you don't own me", "who i am", "i feel alive", "there is no choice",
        "see you around", "have a nice life", "i'm done", "we're done",
        "it ends here", "rest in peace", "not today",
    ],
    "decision_or_climax": [
        "shoot", "pull the trigger", "don't shoot", "spare", "kill him",
        "i have to", "i had no choice", "i won't do it", "i refuse",
        "i made my choice", "i decide", "leave now", "drop your weapon",
        "i surrender", "take me instead", "forgive me", "i can't do that",
        "i must obey", "stand down", "i won't let you", "make your move",
        "let him go", "let her go", "finish it", "fight me", "no more",
    ],
    "revelation_or_truth": [
        "the truth is", "i lied", "you lied to me",
        "all along", "it was you", "i remember", "i know who i am",
        "you're not human", "you're one of us", "you're a deviant",
        "this is who i am", "i finally understand", "now i see",
        "i knew it", "you never cared", "it was all a lie",
    ],
}

# Terminal connector words that indicate an UNFINISHED sentence (Incomplete, NO payoff)
UNFINISHED_SENTENCE_TRAILS = [
    "and", "or", "but", "so", "then", "because", "if", "when", "while",
    "although", "that", "which", "to", "with", "as", "about", "for", "like",
    "uh", "um", "well", "gonna", "wanna",
    # Articles & determiners
    "the", "a", "an", "this", "these", "those", "my", "your", "his", "her", "their", "our", "its",
    # Prepositions
    "into", "onto", "from", "by", "in", "on", "at", "of",
]
