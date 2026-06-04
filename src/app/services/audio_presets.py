# -*- coding: utf-8 -*-
"""
音频预设库 — SFX 音效预设 + 音乐模式预设

供 audio_service.py 导入使用。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .audio_engine import (
    SR, SynthVoice, OscType, EnvShape, ADSRParams, EffectChain,
    MusicPattern,
)


# ============================================================
#  SFX 音效预设库 — 蜂蜜挂机RPG专用
# ============================================================

# ---------- UI 音效 ----------
UI_FX_PRESETS: Dict[str, SynthVoice] = {
    "button_click": SynthVoice(
        freq=800.0, osc_type=OscType.SQUARE, duration=0.06,
        volume=0.6, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=4000, bit_crush=8),
        harmonics=[(1.5, 0.3)],
    ),
    "button_hover": SynthVoice(
        freq=1200.0, osc_type=OscType.SINE, duration=0.04,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=3,
    ),
    "notification": SynthVoice(
        freq=880.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        vibrato_rate=6, vibrato_depth=2,
    ),
    "error": SynthVoice(
        freq=200.0, osc_type=OscType.SQUARE, duration=0.2,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-5,
        effect_chain=EffectChain(distortion=0.2, bit_crush=8),
    ),
    "save_complete": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.15,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.2)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
}

# ---------- 战斗音效 ----------
COMBAT_FX_PRESETS: Dict[str, SynthVoice] = {
    "attack_melee": SynthVoice(
        freq=180.0, osc_type=OscType.NOISE_BROWN, duration=0.15,
        volume=0.75, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=2500, hp_filter_hz=80,
            distortion=0.35, bit_crush=8,
        ),
        harmonics=[(3.0, 0.25)],
    ),
    "attack_magic": SynthVoice(
        freq=1200.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.55, env_shape=EnvShape.SWELL,
        pitch_mod=-8,
        harmonics=[(1.5, 0.35), (2.0, 0.2), (2.5, 0.1)],
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.5, distortion=0.12),
    ),
    "critical_hit": SynthVoice(
        freq=280.0, osc_type=OscType.NOISE_BROWN, duration=0.28,
        volume=0.8, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=3500, distortion=0.45, bit_crush=6, reverb_mix=0.12,
        ),
        harmonics=[(2.0, 0.25), (4.0, 0.12)],
    ),
    "block_hit": SynthVoice(
        freq=320.0, osc_type=OscType.SQUARE, duration=0.07,
        volume=0.6, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-6,
        effect_chain=EffectChain(lp_filter_hz=2000, distortion=0.2, bit_crush=10),
    ),
    "damage_taken": SynthVoice(
        freq=150.0, osc_type=OscType.SAW, duration=0.25,
        volume=0.55, env_shape=EnvShape.REVERSE,
        pitch_mod=-10,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.12, distortion=0.15, stereo_width=0.25,
        ),
    ),
    "dodge": SynthVoice(
        freq=2000.0, osc_type=OscType.NOISE_WHITE, duration=0.07,
        volume=0.3, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=8000, hp_filter_hz=3000),
    ),
    "heal": SynthVoice(
        freq=523.25, osc_type=OscType.SINE, duration=0.45,
        volume=0.48, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(2.0, 0.18), (3.0, 0.08)],
        vibrato_rate=5, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.6),
    ),
    "enemy_death": SynthVoice(
        freq=200.0, osc_type=OscType.SAW, duration=0.5,
        volume=0.55, env_shape=EnvShape.REVERSE,
        pitch_mod=-14,
        effect_chain=EffectChain(
            lp_filter_hz=2500, reverb_mix=0.2, reverb_decay=0.9,
            distortion=0.15, stereo_width=0.4, bit_crush=8,
        ),
        harmonics=[(0.5, 0.25), (1.5, 0.15)],
    ),
    "player_hurt_serious": SynthVoice(
        freq=100.0, osc_type=OscType.SQUARE, duration=0.18,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-5,
        effect_chain=EffectChain(lp_filter_hz=1500, distortion=0.25, bit_crush=8),
    ),
    "shield_gain": SynthVoice(
        freq=450.0, osc_type=OscType.TRIANGLE, duration=0.2,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
        effect_chain=EffectChain(reverb_mix=0.1, lp_filter_hz=4000),
    ),
    "poison_tick": SynthVoice(
        freq=800.0, osc_type=OscType.SINE, duration=0.1,
        volume=0.3, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-2,
        effect_chain=EffectChain(distortion=0.12, bit_crush=10, reverb_mix=0.06),
    ),
}

# ---------- 探索音效 ----------
EXPLORATION_FX_PRESETS: Dict[str, SynthVoice] = {
    "dungeon_enter": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_PINK, duration=0.5,
        volume=0.35, env_shape=EnvShape.SWELL,
        effect_chain=EffectChain(
            lp_filter_hz=3000, reverb_mix=0.2, reverb_decay=0.7, stereo_width=0.4,
        ),
    ),
    "room_clear": SynthVoice(
        freq=440.0, osc_type=OscType.TRIANGLE, duration=0.25,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.1),
        harmonics=[(2.0, 0.15)],
    ),
    "chest_open": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.35,
        volume=0.48, env_shape=EnvShape.SWELL,
        pitch_mod=9,
        harmonics=[(2.0, 0.2), (3.0, 0.08)],
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.5),
    ),
    "loot_pickup": SynthVoice(
        freq=988.0, osc_type=OscType.SINE, duration=0.1,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=2,
    ),
    "item_equip": SynthVoice(
        freq=660.0, osc_type=OscType.TRIANGLE, duration=0.14,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
        harmonics=[(2.0, 0.12)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "landmark_discover": SynthVoice(
        freq=380.0, osc_type=OscType.SINE, duration=0.6,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=12,
        harmonics=[
            (2.0, 0.25), (3.0, 0.12), (4.0, 0.05), (5.0, 0.02),
        ],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(
            reverb_mix=0.25, reverb_decay=0.9, stereo_width=0.5, lp_filter_hz=5000,
        ),
    ),
    "potion_pickup": SynthVoice(
        freq=392.0, osc_type=OscType.SINE, duration=0.25,
        volume=0.42, env_shape=EnvShape.SWELL,
        pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.12, reverb_decay=0.4),
    ),
    "travel_region": SynthVoice(
        freq=350.0, osc_type=OscType.SINE, duration=0.4,
        volume=0.35, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.6, stereo_width=0.3),
    ),
    "elite_alert": SynthVoice(
        freq=740.0, osc_type=OscType.SQUARE, duration=0.28,
        volume=0.48, env_shape=EnvShape.PERCUSSIVE,
        vibrato_rate=6, vibrato_depth=1.5,
        effect_chain=EffectChain(distortion=0.12, bit_crush=10),
    ),
    "dungeon_cleared": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.7,
        volume=0.52, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(1.5, 0.18), (2.0, 0.22), (2.5, 0.1)],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.22, reverb_decay=1.0, stereo_width=0.4),
    ),
    "infestation_warning": SynthVoice(
        freq=150.0, osc_type=OscType.SAW, duration=0.45,
        volume=0.4, env_shape=EnvShape.REVERSE,
        pitch_mod=-6,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.18, distortion=0.15, stereo_width=0.35,
        ),
    ),
}

# ---------- 系统事件音效 ----------
SYSTEM_FX_PRESETS: Dict[str, SynthVoice] = {
    "level_up": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.7,
        volume=0.55, env_shape=EnvShape.SWELL,
        harmonics=[(2.0, 0.28), (3.0, 0.14)],
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.8, stereo_width=0.3),
    ),
    "achievement_unlock": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.9,
        volume=0.5, env_shape=EnvShape.SWELL,
        harmonics=[
            (1.5, 0.18), (2.0, 0.26), (2.5, 0.14), (3.0, 0.08), (4.0, 0.03),
        ],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.22, reverb_decay=1.0, stereo_width=0.38),
    ),
    "gold_gain": SynthVoice(
        freq=988.0, osc_type=OscType.SINE, duration=0.1,
        volume=0.42, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=2,
    ),
    "exp_gain": SynthVoice(
        freq=700.0, osc_type=OscType.TRIANGLE, duration=0.12,
        volume=0.38, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
    ),
    "member_resurrect": SynthVoice(
        freq=330.0, osc_type=OscType.SINE, duration=0.4,
        volume=0.45, env_shape=EnvShape.SWELL,
        pitch_mod=5,
        harmonics=[(2.0, 0.15), (3.0, 0.06)],
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.5),
    ),
    "member_fallen": SynthVoice(
        freq=120.0, osc_type=OscType.SAW, duration=0.35,
        volume=0.42, env_shape=EnvShape.REVERSE,
        pitch_mod=-10,
        effect_chain=EffectChain(lp_filter_hz=1800, reverb_mix=0.15, distortion=0.12)),
    "quest_complete": SynthVoice(
        freq=660.0, osc_type=OscType.TRIANGLE, duration=0.55,
        volume=0.48, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(2.0, 0.2), (3.0, 0.08)],
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.7),
    ),
    "artifact_found": SynthVoice(
        freq=800.0, osc_type=OscType.SINE, duration=0.8,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=12,
        harmonics=[
            (2.0, 0.3), (3.0, 0.18), (4.0, 0.08), (5.0, 0.03), (6.0, 0.01),
        ],
        vibrato_rate=5, vibrato_depth=2.5,
        effect_chain=EffectChain(
            reverb_mix=0.28, reverb_decay=1.2, stereo_width=0.5, lp_filter_hz=5000,
        ),
    ),
    "castle_built": SynthVoice(
        freq=350.0, osc_type=OscType.TRIANGLE, duration=0.6,
        volume=0.48, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(2.0, 0.2), (3.0, 0.08), (4.0, 0.03)],
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.8, stereo_width=0.35),
    ),
    "farm_income": SynthVoice(
        freq=520.0, osc_type=OscType.SINE, duration=0.08,
        volume=0.3, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=2,
    ),
}

ALL_SFX_PRESETS: Dict[str, Dict[str, SynthVoice]] = {
    "ui": UI_FX_PRESETS,
    "combat": COMBAT_FX_PRESETS,
    "exploration": EXPLORATION_FX_PRESETS,
    "system": SYSTEM_FX_PRESETS,
}


# ============================================================
#  音乐模式预设 — 挂机RPG场景音乐
# ============================================================

# --- 探索/挂机 BGM ---
EXPLORATION_MUSIC = MusicPattern(
    name="exploration",
    notes=["C4", "Eb4", "G4", "C5",
           "Bb4", "G4", "Eb4", "C4",
           "Ab4", "C5", "Bb4", "G4",
           "Eb4", "C4", None, "G4"],
    durations=[1.0, 0.5, 0.5, 1.0,
               0.5, 0.5, 1.0, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 1.0],
    octave_shifts=[0]*16,
    bpm=72,
    loop=True,
    osc_type=OscType.TRIANGLE,
    volume=0.10,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.15), (3.0, 0.06)],
    vibrato_rate=3.5,
    vibrato_depth=1,
    reverb_mix=0.25,
    reverb_decay=1.0,
    stereo_width=0.4,
    lp_filter_hz=3500,
)

# --- 战斗 BGM ---
BATTLE_MUSIC = MusicPattern(
    name="battle",
    notes=["C3", None, "G3", None,
           "Eb3", None, "Bb3", None,
           "C3", None, "G3", "Eb3",
           None, "C3", None, None],
    durations=[0.75, 0.25, 0.75, 0.25,
               0.75, 0.25, 0.75, 0.25,
               0.5, 0.25, 0.5, 0.5,
               0.5, 1.0, 0.5, 0.5],
    bpm=110,
    loop=True,
    osc_type=OscType.SAW,
    volume=0.12,
    env_shape=EnvShape.PAD,
    harmonics=[(0.5, 0.12), (2.0, 0.08)],
    vibrato_rate=3,
    vibrato_depth=1,
    reverb_mix=0.12,
    stereo_width=0.3,
    lp_filter_hz=3000,
)

# --- 商人/城镇 BGM ---
TOWN_MUSIC = MusicPattern(
    name="town",
    notes=["C4", "Eb4", "G4", "Eb4",
           "C4", "Bb3", "C4", None,
           "Eb4", "G4", "Bb4", "G4",
           "Eb4", "C4", None, None],
    durations=[0.66, 0.34, 0.5, 0.5,
               0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5,
               1.0, 0.5, 1.0, 0.5],
    bpm=95,
    loop=True,
    osc_type=OscType.SINE,
    volume=0.11,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.12), (3.0, 0.04), (5.0, 0.02)],
    vibrato_rate=5,
    vibrato_depth=1.5,
    reverb_mix=0.18,
    stereo_width=0.35,
)

# --- 休息/篝火 BGM ---
REST_MUSIC = MusicPattern(
    name="rest",
    notes=["G4", None, "E4", None,
           "C4", None, "E4", "G4",
           "A4", None, "E4", "C4",
           None, "D4", None, None],
    durations=[1.0, 0.5, 1.0, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 1.5, 0.5, 0.5],
    bpm=65,
    loop=True,
    osc_type=OscType.SINE,
    volume=0.09,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.10), (3.0, 0.04)],
    vibrato_rate=3,
    vibrato_depth=0.8,
    reverb_mix=0.3,
    reverb_decay=1.2,
    stereo_width=0.5,
    lp_filter_hz=3200,
)

# --- 胜利/事件 BGM ---
VICTORY_MUSIC = MusicPattern(
    name="victory",
    notes=["C5", None, "E5", "G5",
           "C5", "Bb4", "C5", None,
           "G5", "E5", "C5", "Bb4",
           "C5", None, None, None],
    durations=[0.75, 0.25, 0.5, 0.5,
               0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5,
               1.0, 0.5, 1.0, 0.5],
    bpm=95,
    loop=True,
    osc_type=OscType.TRIANGLE,
    volume=0.15,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.22), (3.0, 0.08), (4.0, 0.03)],
    vibrato_rate=5,
    vibrato_depth=2,
    reverb_mix=0.25,
    stereo_width=0.5,
    lp_filter_hz=5000,
)

ALL_MUSIC_PATTERNS: Dict[str, MusicPattern] = {
    "exploration": EXPLORATION_MUSIC,
    "battle": BATTLE_MUSIC,
    "town": TOWN_MUSIC,
    "rest": REST_MUSIC,
    "victory": VICTORY_MUSIC,
}
