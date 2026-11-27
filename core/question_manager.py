"""
Scene-Aware & Non-Repeating Engaging Questions Manager.
Generates AniDoc-style top-header hooks: "Setup Premise | Debate Question?"
Positioned at the top of 1:1 Square Shorts with zero repetition tracked in question_history.json.
"""
import json
import os
import random
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from config.settings import ROOT_DIR

QUESTION_HISTORY_FILE = os.path.join(ROOT_DIR, "question_history.json")

# Curated concise, punchy debate questions (reference style xoJydV-xKVw)
GAME_QUESTIONS_CATALOG: Dict[str, List[str]] = {
    "detroit_become_human": [
        "DID CONNOR BECOME DEVIANT OR OBEY ORDERS?",
        "WAS CONNOR JUST A MACHINE ALL ALONG?",
        "WOULD YOU SPARE OR SHOOT CHLOE?",
        "SHOULD ANDROIDS BE GIVEN EQUAL RIGHTS?",
        "DID CONNOR SACRIFICE HIMSELF FOR THE CAUSE?",
        "IS CONNOR THE BEST WRITTEN ANDROID IN GAMING?",
    ],
    "gta_v": [
        "DID DEVIN WESTON DESERVE THIS ENDING?",
        "COULD TREVOR EVER FORGIVE THIS LIE?",
        "IS THIS THE BEST ENDING IN GTA HISTORY?",
        "WAS SAVING BOTH PROTAGONISTS CANON?",
        "WHO WAS THE MOST EVIL VILLAIN IN GTA V?",
        "WAS MICHAEL RIGHT TO FAKE HIS DEATH?",
    ],
    "red_dead_redemption_2": [
        "DID ARTHUR MORGAN DESERVE THIS REDEMPTION?",
        "IS THIS THE GREATEST STORY IN GAMING HISTORY?",
        "DID DUTCH FINALLY REALIZE MICAH'S BETRAYAL?",
        "COULD THE VAN DER LINDE GANG EVER SURVIVE?",
        "WAS MICAH THE MOST HATED VILLAIN IN GAMING?",
        "WAS ARTHUR'S SACRIFICE WORTH IT?",
    ],
    "god_of_war_ragnarok": [
        "WHO DELIVERED THE COLDEST BLOW?",
        "WAS RAGNAROK UNAVOIDABLE FROM THE START?",
        "CAN ANYONE TRULY CHANGE THEIR FATE?",
        "DID KRATOS DESERVE FORGIVENESS?",
        "WAS ODIN THE COLDEST VILLAIN IN GAMING?",
    ],
    "cyberpunk_2077": [
        "WAS THERE ANY HAPPY ENDING IN NIGHT CITY?",
        "WOULD YOU SEND SONGBIRD TO THE MOON?",
        "IS THIS THE COLDEST MISSION IN GAMING?",
        "WAS DUTY WORTH GIVING UP FREEDOM?",
        "WHO WAS MORE SELFISH IN NIGHT CITY?",
    ],
    "the_last_of_us": [
        "WAS JOEL RIGHT TO SAVE ELLIE?",
        "WOULD YOU SACRIFICE ONE TO SAVE EVERYONE?",
        "DID ELLIE ALREADY KNOW THE TRUTH?",
        "WAS JOEL'S RAGE JUSTIFIED?",
    ],
    "gta_6": [
        "WILL LUCIA OR JASON BETRAY EACH OTHER?",
        "IS GTA 6 THE GREATEST GAME EVER MADE?",
        "COULD THEY SURVIVE VICE CITY TOGETHER?",
        "WOULD YOU TRUST LUCIA IN THIS HEIST?",
        "WAS TRUST THEIR ONLY FATAL MISTAKE?",
        "IS THIS THE MOST REALISTIC GRAPHICS IN GAMING?",
    ],
}


class QuestionManager:
    """Manages scene-specific engaging questions and guarantees zero repetition across runs."""

    def __init__(self, history_file: str = QUESTION_HISTORY_FILE):
        self.history_file = history_file

    def load_history(self) -> List[str]:
        if not os.path.isfile(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def record_question(self, question: str) -> None:
        """Appends question to history file."""
        history = self.load_history()
        cleaned = question.strip()
        if cleaned and cleaned not in history:
            history.append(cleaned)
            try:
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Warning: Failed to save question history: {e}")

    def generate_question(
        self,
        game_key: str,
        game_name: str,
        cutscene_title: str = "",
        characters: Optional[List[str]] = None,
    ) -> str:
        """
        Picks or synthesizes a fresh, non-repeating AniDoc-style top engaging question:
        'Setup Premise before drop | Debate Question after drop?'
        """
        history = set(self.load_history())

        # 1. Try curated questions for this game
        normalized_key = game_key.lower().replace("-", "_").replace(" ", "_")
        candidates = GAME_QUESTIONS_CATALOG.get(normalized_key, [])
        unseen = [q for q in candidates if q not in history]

        if unseen:
            chosen = random.choice(unseen)
            self.record_question(chosen)
            return chosen

        # 2. Synthesize dynamically from cutscene title & characters
        clean_title = re.sub(r"(?i)\b(4k|60fps|cutscene|all endings|full movie|part \d+)\b", "", cutscene_title)
        clean_title = re.sub(r"[^A-Za-z0-9 ]+", " ", clean_title).strip()
        premise = clean_title.upper() if len(clean_title) >= 10 else f"{game_name.upper()} STORY CLIMAX"

        lead_char = characters[0] if (characters and len(characters) > 0) else "HE"
        debate_options = [
            f"DID {lead_char.upper()} MAKE THE RIGHT CHOICE?",
            f"COULD ANYONE SURVIVE THIS CONFRONTATION?",
            f"WAS THIS THE COLDEST MOMENT IN {game_name.upper()}?",
            f"DID THIS CHARACTER DESERVE THIS ENDING?",
            f"WOULD YOU SACRIFICE EVERYTHING HERE?",
        ]

        for debate in debate_options:
            q = f"{premise} | {debate}"
            if q not in history:
                self.record_question(q)
                return q

        # Fallback if every combination was used
        fallback = f"{game_name.upper()} CUTSCENE CLIMAX | WAS THIS THE PEAK DECISION?"
        self.record_question(fallback)
        return fallback
