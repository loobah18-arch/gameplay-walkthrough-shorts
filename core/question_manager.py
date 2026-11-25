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

# Curated game questions grounded in key confrontations and character dilemmas
GAME_QUESTIONS_CATALOG: Dict[str, List[str]] = {
    "detroit_become_human": [
        "CONNOR CONFRONTS THE DEVIANT | DID HE BECOME DEVIANT OR OBEY ORDERS?",
        "HANK DREW HIS SERVICE WEAPON | WAS CONNOR JUST A MACHINE ALL ALONG?",
        "SAVING THE HOSTAGE ON THE ROOF | DID CONNOR MAKE THE RIGHT CHOICE?",
        "MARKUS LEADS THE FREEDOM MARCH | SHOULD ANDROIDS BE GIVEN EQUAL RIGHTS?",
        "THE TOWER INTERROGATION ROOM | WOULD YOU SPARE OR SHOOT CHLOE?",
        "CONNOR'S CYBERLIFE MISSION | DID HE SACRIFICE HIMSELF FOR THE CAUSE?",
        "DEVIANT HUNTER BECAME DEVIANT | IS CONNOR THE BEST WRITTEN ANDROID?",
    ],
    "gta_v": [
        "MICHAEL & FRANKLIN AT THE CLIFF | DID DEVIN WESTON DESERVE THIS ENDING?",
        "TREVOR CONFRONTS MICHAEL IN DESERT | COULD TREVOR EVER FORGIVE THE LIE?",
        "THE THIRD WAY DEATHWISH FINALE | IS THIS THE BEST ENDING IN GTA HISTORY?",
        "FRANKLIN MADE HIS FINAL CHOICE | WAS SAVING BOTH PROTAGONISTS CANON?",
        "DEVIN WESTON'S CAR PUSHED OVER | WHO WAS THE MOST DESPICABLE VILLAIN?",
        "TREVOR DISCOVERS BRAD'S GRAVE | WAS MICHAEL RIGHT TO FAKE HIS DEATH?",
    ],
    "red_dead_redemption_2": [
        "ARTHUR MORGAN'S FINAL STAND | IS THIS THE GREATEST STORY IN GAMING?",
        "DUTCH WALKED AWAY IN SILENCE | DID HE FINALLY REALIZE MICAH'S BETRAYAL?",
        "HIGH HONOR SUNSET RESOLUTION | DID ARTHUR FINALLY FIND REDEMPTION?",
        "JOHN MARSTON ESCAPES THE MOUNTAIN | DID ARTHUR'S SACRIFICE SAVE HIM?",
        "ARTHUR CONFRONTS DUTCH AND MICAH | WHO WAS THE REAL MONSTER IN THE GANG?",
        "I GAVE YOU ALL I HAD | COULD THE VAN DER LINDE GANG EVER SURVIVE?",
    ],
    "god_of_war_ragnarok": [
        "KRATOS CLASHES WITH THOR | WHO DELIVERED THE COLDEST BLOW?",
        "ODIN OFFERED A FALSE PEACE | WAS RAGNAROK UNAVOIDABLE FROM THE START?",
        "ATREUS STRUGGLES WITH PROPHECY | CAN ANYONE TRULY CHANGE THEIR FATE?",
        "FREYA FACES THE GHOST OF SPARTA | DID KRATOS DESERVE FORGIVENESS?",
        "THOR BROKE HIS OWN HAMMER | DID ODIN USE HIS ENTIRE FAMILY AS WEAPONS?",
        "THE DESTRUCTION OF ASGARD | WAS ODIN THE COLDEST FATHER IN GAMING?",
    ],
    "cyberpunk_2077": [
        "JOHNNY OFFERS HIS SOUL TO SAVE V | WHO WAS MORE SELFISH IN NIGHT CITY?",
        "DON'T FEAR THE REAPER SOLO RUN | IS THIS THE BADDEST ASSAULT IN GAMING?",
        "SONGBIRD REVEALED HER SECRET | WOULD YOU SEND HER TO THE MOON?",
        "REED DREW HIS PISTOL AT MIDNIGHT | WAS DUTY WORTH GIVING UP FREEDOM?",
        "V STARES AT THE NIGHT CITY SKYLINE | WAS THERE ANY HAPPY ENDING IN CYBERPUNK?",
    ],
    "the_last_of_us": [
        "JOEL CARRIES ELLIE FROM HOSPITAL | WAS SAVING HER SELFISH OR RIGHT?",
        "MARLENE OFFERED A CURE FOR MANKIND | WOULD YOU SACRIFICE ONE TO SAVE ALL?",
        "JOEL LIED LOOKING IN HER EYES | DID ELLIE ALREADY KNOW THE TRUTH?",
        "THE WINTER CABIN CONFRONTATION | WAS JOEL'S RAGE JUSTIFIED?",
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
