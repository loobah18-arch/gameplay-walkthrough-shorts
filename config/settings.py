"""
Configuration settings for Gameplay Walkthrough Shorts Clipper.
"""
import os
from typing import Dict, Any

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Default GitHub Repo & Action Workflow for Cloud Dispatch
DEFAULT_GITHUB_REPO = "loobah18-arch/gameplay-walkthrough-shorts"
DEFAULT_WORKFLOW_FILE = "render_walkthrough_short.yml"

# Aspect Ratio Presets
# Reference style (https://youtube.com/shorts/kepvkxTGqVM) uses high-resolution 1:1 square
ASPECT_RATIOS: Dict[str, Dict[str, Any]] = {
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

DEFAULT_ASPECT_RATIO = "square"

# Subtitle Styling Constants (ASS Format)
SUBTITLE_STYLE = {
    "font_name": "Montserrat",
    "fallback_font": "DejaVu Sans",
    "font_size_square": 46,
    "font_size_vertical": 54,
    "primary_color": "&H00FFFFFF&",    # Crisp white text
    "highlight_color": "&H0000D4FF&",  # Warm golden amber / yellow for active keywords
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
