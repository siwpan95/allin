# -*- coding: utf-8 -*-
"""
音频合成引擎 - 振荡器 / 包络 / 效果链 / 合成核心

供 audio_service.py 和 audio_presets.py 使用。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
try:
    from scipy.io import wavfile
except ImportError:
    from scipy import wavfile

# ============================================================
#  全局参数
# ============================================================
SR = 44100  # 采样率


# ============================================================
#  音符频率表
# ============================================================
_NOTES = {}
for _i, _n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]):
    for _oct in range(2, 7):
        _key = f"{_n}{_oct}"
        _freq = 440.0 * (2 ** ((_i - 9) / 12.0 + (_oct - 4)))
        _NOTES[_key] = round(_freq, 2)


def note_to_freq(note: str) -> float:
    return _NOTES.get(note, 440.0)


# ============================================================
#  振荡器模块
# ============================================================
class OscType(Enum):
    SAW = "saw"
    SQUARE = "square"
    SINE = "sine"
    TRIANGLE = "triangle"
    NOISE_WHITE = "noise_white"
    NOISE_PINK = "noise_pink"
    NOISE_BROWN = "noise_brown"


def osc_saw(t: np.ndarray, freq: float) -> np.ndarray:
    return 2.0 * ((t * freq) % 1.0) - 1.0


def osc_square(t: np.ndarray, freq: float, duty: float = 0.5) -> np.ndarray:
    return np.where(((t * freq) % 1.0) < duty, 1.0, -1.0)


def osc_sine(t: np.ndarray, freq: float) -> np.ndarray:
    return np.sin(2.0 * np.pi * t * freq)


def osc_triangle(t: np.ndarray, freq: float) -> np.ndarray:
    phase = (t * freq) % 1.0
    return 4.0 * np.abs(phase - 0.5) - 1.0


def _pink_noise_kernel(n: int) -> np.ndarray:
    out = np.zeros(n)
    states = np.zeros(12)
    for i in range(n):
        inc = np.random.randn()
        idx = i & (len(states) - 1)
        states[idx] = 0.998 * states[idx] + inc
        out[i] = states.mean() + inc * 0.05
    return out * 3.0


def osc_noise_white(n: int) -> np.ndarray:
    return 2.0 * np.random.random(n) - 1.0


def osc_noise_pink(n: int) -> np.ndarray:
    return _pink_noise_kernel(n)


def osc_noise_brown(n: int) -> np.ndarray:
    out = np.cumsum(2.0 * np.random.random(n) - 1.0)
    out = out / (np.max(np.abs(out)) + 1e-8)
    return out


def oscillator(t: np.ndarray, freq: float, osc_type: OscType = OscType.SAW,
               duty: float = 0.5) -> np.ndarray:
    if osc_type == OscType.SAW:
        return osc_saw(t, freq)
    elif osc_type == OscType.SQUARE:
        return osc_square(t, freq, duty)
    elif osc_type == OscType.SINE:
        return osc_sine(t, freq)
    elif osc_type == OscType.TRIANGLE:
        return osc_triangle(t, freq)
    elif osc_type == OscType.NOISE_WHITE:
        return osc_noise_white(len(t))
    elif osc_type == OscType.NOISE_PINK:
        return osc_noise_pink(len(t))
    elif osc_type == OscType.NOISE_BROWN:
        return osc_noise_brown(len(t))
    else:
        return osc_saw(t, freq)


# ============================================================
#  包络模块
# ============================================================
class EnvShape(Enum):
    PERCUSSIVE = "percussive"
    PAD = "pad"
    PLUCK = "pluck"
    SWELL = "swell"
    REVERSE = "reverse"
    ADSR_CUSTOM = "adsr_custom"


@dataclass
class ADSRParams:
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.15


# ============================================================
#  音乐模式数据类
# ============================================================
@dataclass
class MusicPattern:
    """音乐模式预设 — 定义一段循环旋律的完整合成参数。"""
    name: str
    notes: List[Optional[str]]
    durations: List[float]
    bpm: int = 90
    loop: bool = True
    osc_type: OscType = OscType.TRIANGLE
    volume: float = 0.10
    env_shape: EnvShape = EnvShape.PAD
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    vibrato_rate: float = 4.0
    vibrato_depth: float = 1.0
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    stereo_width: float = 0.3
    octave_shifts: Optional[List[int]] = None
    lp_filter_hz: Optional[float] = None

    def __post_init__(self):
        if self.octave_shifts is None:
            self.octave_shifts = [0] * len(self.notes)


def make_envelope(length: int, shape: EnvShape = EnvShape.PERCUSSIVE,
                 adsr: Optional[ADSRParams] = None,
                 custom_peak: float = 1.0) -> np.ndarray:
    if length <= 0:
        return np.array([0.0])

    e = np.ones(length)

    if shape == EnvShape.PERCUSSIVE:
        att = max(1, int(0.003 * length))
        dec = max(1, int(0.15 * length))
        rel = max(1, int(0.20 * length))
        e[:att] = np.linspace(0, 1, att)
        e[att:att + dec] = np.linspace(1, 0.15, dec)
        e[-rel:] = np.linspace(e[-rel] if rel < length else 0.15, 0, rel)

    elif shape == EnvShape.PAD:
        att = max(1, int(0.20 * length))
        rel = max(1, int(0.30 * length))
        sus_val = 0.85
        e[:att] = np.linspace(0, sus_val, att)
        e[-rel:] = np.linspace(sus_val, 0, rel)

    elif shape == EnvShape.PLUCK:
        att = max(1, int(0.002 * length))
        dec = max(int(1), int(0.40 * length))
        e[:att] = np.linspace(0, 1, att)
        dec_curve = np.exp(-np.linspace(0, 5, dec))
        end_idx = min(att + dec, length)
        e[att:end_idx] *= dec_curve[:end_idx - att]
        if end_idx < length:
            e[end_idx:] *= 0.001

    elif shape == EnvShape.SWELL:
        half = length // 2
        e[:half] = np.linspace(0, 1, half)
        e[half:] = np.linspace(1, 0, length - half)

    elif shape == EnvShape.REVERSE:
        rel = max(1, int(0.70 * length))
        e[:length - rel] = 1.0
        e[length - rel:] = np.linspace(1, 0, rel)

    elif shape == EnvShape.ADSR_CUSTOM and adsr is not None:
        att_samp = int(adsr.attack * SR)
        dec_samp = int(adsr.decay * SR)
        rel_samp = int(adsr.release * SR)
        att_samp = min(att_samp, length // 4)
        dec_samp = min(dec_samp, length // 4)
        rel_samp = min(rel_samp, length // 4)

        pos = 0
        if att_samp > 0:
            e[pos:pos + att_samp] = np.linspace(0, 1, att_samp)
            pos += att_samp
        if dec_samp > 0:
            end_d = min(pos + dec_samp, length - rel_samp)
            e[pos:end_d] = np.linspace(1, adsr.sustain, end_d - pos)
            pos = end_d
        if pos < length - rel_samp:
            e[pos:length - rel_samp] = adsr.sustain
        if rel_samp > 0:
            e[length - rel_samp:] = np.linspace(
                e[length - rel_samp] if rel_samp < length else adsr.sustain,
                0, rel_samp)

    return e * custom_peak


# ============================================================
#  效果链模块
# ============================================================
@dataclass
class EffectChain:
    lp_filter_hz: Optional[float] = None
    hp_filter_hz: Optional[float] = None
    distortion: float = 0.0
    bit_crush: int = 16
    reverb_mix: float = 0.0
    reverb_decay: float = 0.3
    stereo_width: float = 0.0


def apply_lowpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    output = np.zeros_like(sig)
    output[0] = sig[0]
    for i in range(1, len(sig)):
        output[i] = alpha * sig[i] + (1 - alpha) * output[i - 1]
    return output


def apply_highpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    lp = apply_lowpass(sig, cutoff_hz, sr)
    return sig - lp


def apply_distortion(sig: np.ndarray, amount: float = 0.5) -> np.ndarray:
    if amount <= 0:
        return sig
    drive = 1.0 + amount * 10.0
    return np.tanh(sig * drive) / np.tanh(drive)


def apply_bit_crush(sig: np.ndarray, depth: int = 8) -> np.ndarray:
    if depth >= 16:
        return sig
    steps = 2 ** depth
    quantized = np.round(sig * (steps / 2)) / (steps / 2)
    return np.clip(quantized, -1, 1)


def apply_simple_reverb(sig: np.ndarray, mix: float = 0.2,
                        decay: float = 0.3, sr: int = SR) -> np.ndarray:
    if mix <= 0 or len(sig) < sr:
        return sig

    delay_samples = [
        int(sr * 0.047), int(sr * 0.071),
        int(sr * 0.113), int(sr * 0.173),
    ]
    gains = [0.55, 0.43, 0.32, 0.21]

    wet = np.zeros_like(sig)
    for dly, gain in zip(delay_samples, gains):
        if dly >= len(sig):
            continue
        delayed = np.zeros_like(sig)
        delayed[dly:] = sig[:-dly] * gain * np.exp(
            -np.arange(len(sig) - dly) * (1.0 / (decay * sr)))
        wet += delayed

    wet_norm = wet / (np.max(np.abs(wet)) + 1e-8)
    wet_lp = apply_lowpass(wet_norm, 4000)

    return sig * (1 - mix) + wet_lp * mix


def apply_stereo(sig: np.ndarray, width: float = 0.5) -> np.ndarray:
    if width <= 0 or (sig.ndim > 1 and sig.shape[1] == 2):
        return sig

    mid = sig.copy()
    rng = np.random.RandomState(seed=42)
    n = len(sig)
    chunk_size = max(n // 64, 8)
    n_chunks = (n + chunk_size - 1) // chunk_size
    lowres_noise = rng.randn(max(n_chunks, 2))
    xp = np.linspace(0, n, len(lowres_noise))
    side = np.interp(np.arange(n), xp, lowres_noise)
    side = side / (np.max(np.abs(side)) + 1e-8) * width * mid * 0.3

    kernel_size = min(256, max(n // 20, 4))
    if kernel_size >= 2:
        kernel = np.ones(kernel_size) / kernel_size
        side = np.convolve(side, kernel, mode='same')

    left = mid + side
    right = mid - side
    return np.column_stack([left, right])


def process_effects(sig: np.ndarray, chain: EffectChain) -> np.ndarray:
    result = sig.copy()
    if chain.lp_filter_hz is not None:
        result = apply_lowpass(result, chain.lp_filter_hz)
    if chain.hp_filter_hz is not None:
        result = apply_highpass(result, chain.hp_filter_hz)
    if chain.distortion > 0:
        result = apply_distortion(result, chain.distortion)
    if chain.bit_crush < 16:
        result = apply_bit_crush(result, chain.bit_crush)
    if chain.reverb_mix > 0:
        result = apply_simple_reverb(result, chain.reverb_mix, chain.reverb_decay)
    if chain.stereo_width > 0:
        result = apply_stereo(result, chain.stereo_width)
    return result


# ============================================================
#  合成核心
# ============================================================
@dataclass
class SynthVoice:
    """单音合成参数"""
    freq: float = 440.0
    osc_type: OscType = OscType.SINE
    duration: float = 0.15
    volume: float = 1.0
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional[EffectChain] = None
    pitch_mod: float = 0.0
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0
    detune: float = 0.0
    harmonics: List[Tuple[float, float]] = field(default_factory=list)


def synthesize_voice(voice: SynthVoice) -> np.ndarray:
    """合成单个声音，返回 float32 数组"""
    n_samples = int(voice.duration * SR)
    if n_samples <= 0:
        n_samples = 1

    t = np.linspace(0, voice.duration, n_samples, dtype=np.float64)
    base_freq = voice.freq * (2 ** (voice.pitch_mod / 12))

    if voice.vibrato_depth > 0 and voice.vibrato_rate > 0:
        vib = 1.0 + (voice.vibrato_depth / 12) * np.sin(
            2 * np.pi * voice.vibrato_rate * t) * make_envelope(
            n_samples, EnvShape.PAD)[:n_samples]
        mod_freq = base_freq * vib
    else:
        mod_freq = base_freq

    main_sig = oscillator(t, mod_freq, voice.osc_type)

    for harmonic_mult, harmonic_amp in voice.harmonics:
        h_freq = mod_freq * harmonic_mult
        h_sig = oscillator(t, h_freq, voice.osc_type) * harmonic_amp
        main_sig += h_sig

    if abs(voice.detune) > 0.001:
        detune_sig = oscillator(
            t, mod_freq * (2 ** (voice.detune / 12)), voice.osc_type) * 0.6
        main_sig += detune_sig

    env = make_envelope(n_samples, voice.env_shape, voice.adsr)
    sig = main_sig * env * voice.volume

    if voice.effect_chain is not None:
        sig = process_effects(sig, voice.effect_chain)

    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak * 0.98

    return sig.astype(np.float32)


def generate_music_wav(pattern, output_path: str,
                       duration_sec: Optional[float] = None) -> str:
    """根据 MusicPattern 生成并写入 WAV 文件"""
    beat_dur = 60.0 / pattern.bpm
    all_notes = []
    total_beats = sum(pattern.durations)

    if duration_sec is None:
        loops = 2 if pattern.loop else 1
    else:
        loops = max(1, int(duration_sec / (total_beats * beat_dur)))

    octaves = pattern.octave_shifts or [0] * len(pattern.notes)

    for loop_idx in range(loops):
        for i, note in enumerate(pattern.notes):
            dur = pattern.durations[i] * beat_dur
            oct_v = octaves[i] if i < len(octaves) else 0
            all_notes.append((note, dur, oct_v))

    samples_list = []
    for note, dur, oct_v in all_notes:
        n_samp = int(dur * SR)
        t = np.linspace(0, dur, n_samp, dtype=np.float64)

        if note is None:
            sig = np.zeros(n_samp)
        else:
            f = note_to_freq(note) * (2 ** oct_v)
            sig = oscillator(t, f, pattern.osc_type)
            for h_mult, h_amp in pattern.harmonics:
                sig += oscillator(t, f * h_mult, pattern.osc_type) * h_amp

            if pattern.vibrato_depth > 0:
                vib_env = make_envelope(n_samp, EnvShape.PAD)
                vib = 1.0 + (pattern.vibrato_depth / 12) * np.sin(
                    2 * np.pi * pattern.vibrato_rate * t) * vib_env
                sig = np.zeros(n_samp)
                mod_f = f * vib
                sig = oscillator(t, mod_f, pattern.osc_type)
                for h_mult, h_amp in pattern.harmonics:
                    sig += oscillator(t, mod_f * h_mult, pattern.osc_type) * h_amp

            env = make_envelope(n_samp, pattern.env_shape)
            sig = sig * env * pattern.volume

        samples_list.append(sig)

    full_signal = np.concatenate(samples_list) if samples_list else np.zeros(SR)

    chain = EffectChain(
        reverb_mix=pattern.reverb_mix,
        reverb_decay=pattern.reverb_decay,
        stereo_width=pattern.stereo_width,
        lp_filter_hz=pattern.lp_filter_hz,
    )
    processed = process_effects(full_signal, chain)

    if processed.ndim > 1 and processed.shape[1] >= 2:
        final = processed
    else:
        final = processed.reshape(-1, 1)

    final_int16 = np.clip(final * 32767, -32768, 32767).astype(np.int16)
    wavfile.write(output_path, SR, final_int16)
    return output_path
