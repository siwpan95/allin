#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
  音频制作工作站 (Game Audio Workstation)
  基于 sounddevice + numpy 的程序化音频合成引擎
  Author: GameAudioEngineer
  Version: 2.0.0
============================================

功能:
  - 多波形振荡器 (saw/square/sine/triangle/noise)
  - 多类型包络 (percussive/pad/pluck/swell/reverse)
  - 效果链 (filter/distortion/reverb/stereo)
  - SFX 批量生成
  - 自适应音乐生成 (菜单/战斗/事件/休息)
  - WAV 批量导出 + 实时预览 GUI

用法:
  python faatt.py              # 启动 GUI 工作站
  python faatt.py --batch      # 无GUI批量导出所有音频
  python faatt.py --preview    # 预览特定音效 (开发调试用)
"""

import sounddevice as sd
import numpy as np
from scipy.io import wavfile
import threading
import time
import os
import sys
import argparse
import struct
import random
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Tuple, Dict
from enum import Enum
from pathlib import Path


# ============================================================
#  全局常量
# ============================================================
SR = 44100          # 采样率
BPM = 120           # 默认 BPM (音乐用)
BEAT = 60 / BPM     # 每拍秒数
VOL_SFX = 0.35      # SFX 默认音量
VOL_MUSIC = 0.18    # 音乐默认音量


# ============================================================
#  音符频率表 (扩展到完整八度)
# ============================================================
NOTES: Dict[str, float] = {
    # 低音区 C2-B2
    "C2": 65.41,  "D": 73.42,  "Eb": 77.78,  "E": 82.41,
    "F": 87.31,  "Gb": 92.50, "G": 98.00,   "Ab": 103.83,
    "A": 110.00, "Bb": 116.54,"B": 123.47,
    # 中音区 C3-B3
    "C3": 130.81, "D3": 146.83,"Eb3": 155.56,"E3": 164.81,
    "F3": 174.61,"Gb3": 185.00,"G3": 196.00, "Ab3": 207.65,
    "A3": 220.00, "Bb3": 233.08,"B3": 246.94,
    # 标准音区 C4-B4
    "C4": 261.63, "Db": 277.18,"D4": 293.66, "Eb_4": 311.13,
    "E4": 329.63, "F4": 349.23,"Gb4": 369.99, "G4": 392.00,
    "Ab4": 415.30,"A4": 440.00, "Bb4": 466.16, "B4": 493.88,
    # 高音区 C5-B5
    "C5": 523.25, "Db5": 554.37,"D5": 587.33, "Eb5": 622.25,
    "E5": 659.26, "F5": 698.46,"Gb5": 739.99, "G5": 783.99,
    "Ab5": 830.61,"A5": 880.00, "Bb5": 932.33, "B5": 987.77,
}


def note_to_freq(note: str) -> float:
    """安全获取音符频率，未知音符返回 A4(440Hz)"""
    return NOTES.get(note, 440.0)


# ============================================================
#  振荡器模块 (Oscillators)
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
    """锯齿波 - 丰富谐波，适合金属感/弦乐"""
    return 2.0 * ((t * freq) % 1.0) - 1.0


def osc_square(t: np.ndarray, freq: float, duty: float = 0.5) -> np.ndarray:
    """方波 - 8-bit 复古风格，芯片音乐"""
    return np.where(((t * freq) % 1.0) < duty, 1.0, -1.0)


def osc_sine(t: np.ndarray, freq: float) -> np.ndarray:
    """正弦波 - 纯净音色，适合 UI 提示音、铃声"""
    return np.sin(2.0 * np.pi * t * freq)


def osc_triangle(t: np.ndarray, freq: float) -> np.ndarray:
    """三角波 - 柔和但带泛音，适合木管乐器质感"""
    phase = (t * freq) % 1.0
    return 4.0 * np.abs(phase - 0.5) - 1.0


def _pink_noise_kernel(n: int) -> np.ndarray:
    """Pink noise 生成核 (Voss-McCarthy algorithm)"""
    out = np.zeros(n)
    states = np.zeros(12)
    for i in range(n):
        inc = np.random.randn()
        idx = i & (len(states) - 1)
        states[idx] = 0.998 * states[idx] + inc
        out[i] = states.mean() + inc * 0.05
    return out * 3.0  # 归一化


def osc_noise_white(n: int, rng: np.random.Generator = None) -> np.ndarray:
    """白噪声 - 全频段能量均匀，适合冲击声、爆炸底噪"""
    if rng is None:
        rng = np.random.default_rng()
    return 2.0 * rng.random(n) - 1.0


def osc_noise_pink(n: int) -> np.ndarray:
    """粉红噪声 - 能量随频率递减，适合自然环境音、雨声"""
    return _pink_noise_kernel(n)


def osc_noise_brown(n: int) -> np.ndarray:
    """棕噪声 (随机游走) - 低频主导，适合雷声、低频震动"""
    out = np.cumsum(2.0 * np.random.random(n) - 1.0)
    out = out / (np.max(np.abs(out)) + 1e-8)
    return out


def oscillator(t: np.ndarray, freq: float, osc_type: OscType = OscType.SAW,
               duty: float = 0.5) -> np.ndarray:
    """
    统一振荡器接口
    Args:
        t: 时间数组 (秒)
        freq: 基频 (Hz)
        osc_type: 波形类型
        duty: 方波占空比
    Returns:
        归一化 [-1, 1] 波形数组
    """
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
#  包络模块 (Envelopes)
# ============================================================
class EnvShape(Enum):
    PERCUSSIVE = "percussive"  # 快速起音快速衰减 (打击乐)
    PAD = "pad"                # 慢起慢释 (铺底音色)
    PLUCK = "pluck"            # 瞬时起音中速衰减 (弹拨)
    SWELL = "swell"            # 渐入渐出 (氛围音)
    REVERSE = "reverse"        # 反向包络 (吸气声)
    ADSR_CUSTOM = "adsr_custom" # 自定义 ADSR


@dataclass
class ADSRParams:
    """ADSR 包络参数 (单位: 秒)"""
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.15


def make_envelope(length: int, shape: EnvShape = EnvShape.PERCUSSIVE,
                  adsr: Optional[ADSRParams] = None,
                  custom_peak: float = 1.0) -> np.ndarray:
    """
    生成包络数组
    Args:
        length: 采样点数
        shape: 包络形状
        adsr: 自定义 ADSR 参数
        custom_peak: 包络峰值振幅
    Returns:
        [0, 1] 范围的包络数组
    """
    if length <= 0:
        return np.array([0.0])

    e = np.ones(length)

    if shape == EnvShape.PERCUSSIVE:
        # 快速起音 → 快速衰减，适合点击、打击
        att = max(1, int(0.003 * length))       # 0.3% 起音
        dec = max(1, int(0.15 * length))         # 15% 衰减
        rel = max(1, int(0.20 * length))         # 20% 释放
        e[:att] = np.linspace(0, 1, att)
        e[att:att + dec] = np.linspace(1, 0.15, dec)
        e[-rel:] = np.linspace(e[-rel] if rel < length else 0.15, 0, rel)

    elif shape == EnvShape.PAD:
        # 慢进慢出，适合氛围铺底
        att = max(1, int(0.20 * length))
        rel = max(1, int(0.30 * length))
        sus_val = 0.85
        e[:att] = np.linspace(0, sus_val, att)
        e[-rel:] = np.linspace(sus_val, 0, rel)

    elif shape == EnvShape.PLUCK:
        # 瞬时起音 → 指数衰减，适合卡牌、弹拨
        att = max(1, int(0.002 * length))
        dec = max(int(1), int(0.40 * length))
        e[:att] = np.linspace(0, 1, att)
        dec_curve = np.exp(-np.linspace(0, 5, dec))
        end_idx = min(att + dec, length)
        e[att:end_idx] *= dec_curve[:end_idx - att]
        if end_idx < length:
            e[end_idx:] *= 0.001

    elif shape == EnvShape.SWELL:
        # 渐入渐出对称，适合过渡音效
        half = length // 2
        e[:half] = np.linspace(0, 1, half)
        e[half:] = np.linspace(1, 0, length - half)

    elif shape == EnvShape.REVERSE:
        # 从大声开始衰减（倒放效果）
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
#  效果模块 (Effects)
# ============================================================
@dataclass
class EffectChain:
    """效果链配置"""
    lp_filter_hz: Optional[float] = None      # 低通滤波截止频率 (None=禁用)
    hp_filter_hz: Optional[float] = None      # 高通滤波截止频率
    distortion: float = 0.0                   # 失真量 (0-1)
    bit_crush: int = 16                       # 位压缩深度 (16=无效果, 4-8=强烈)
    reverb_mix: float = 0.0                   # 混响混合比 (0-0.4)
    reverb_decay: float = 0.3                 # 混响衰减时间(秒)
    stereo_width: float = 0.0                 # 立体声宽度 (0=单声道, 1=全宽)


def apply_lowpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    """简单 1 极点 RC 低通滤波器"""
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    output = np.zeros_like(sig)
    output[0] = sig[0]
    for i in range(1, len(sig)):
        output[i] = alpha * sig[i] + (1 - alpha) * output[i - 1]
    return output


def apply_highpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    """高通滤波 (信号 - 低通)"""
    lp = apply_lowpass(sig, cutoff_hz, sr)
    return sig - lp


def apply_distortion(sig: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """软削波失真 (tanh)"""
    if amount <= 0:
        return sig
    drive = 1.0 + amount * 10.0
    return np.tanh(sig * drive) / np.tanh(drive)


def apply_bit_crush(sig: np.ndarray, depth: int = 8) -> np.ndarray:
    """位压缩效果 (降低量化位数)"""
    if depth >= 16:
        return sig
    steps = 2 ** depth
    quantized = np.round(sig * (steps / 2)) / (steps / 2)
    return np.clip(quantized, -1, 1)


def apply_simple_reverb(sig: np.ndarray, mix: float = 0.2,
                        decay: float = 0.3, sr: int = SR) -> np.ndarray:
    """
    简单多延迟线混响模拟
    使用 4 条不同延迟时间的延迟线 + 低通反馈
    """
    if mix <= 0 or len(sig) < sr:
        return sig

    delay_samples = [
        int(sr * 0.047),   # ~47ms
        int(sr * 0.071),   # ~71ms
        int(sr * 0.113),   # ~113ms
        int(sr * 0.173),   # ~173ms
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

    # 湿信号轻微低通
    wet_norm = wet / (np.max(np.abs(wet)) + 1e-8)
    wet_lp = apply_lowpass(wet_norm, 4000)

    return sig * (1 - mix) + wet_lp * mix


def apply_stereo(sig: np.ndarray, width: float = 0.5) -> np.ndarray:
    """将单声道扩展为立体声 (M-S 编码)"""
    if width <= 0 or len(sig.shape) > 1 and sig.shape[1] == 2:
        return sig

    mid = sig.copy()
    # 使用平滑随机调制生成立体声侧边信号
    rng = np.random.RandomState(seed=42)
    n = len(sig)
    # 生成低分辨率噪声并插值到全尺寸
    chunk_size = max(n // 64, 8)
    n_chunks = (n + chunk_size - 1) // chunk_size
    lowres_noise = rng.randn(max(n_chunks, 2))
    xp = np.linspace(0, n, len(lowres_noise))
    fp = lowres_noise
    side = np.interp(np.arange(n), xp, fp)
    # 归一化并缩放
    side = side / (np.max(np.abs(side)) + 1e-8) * width * mid * 0.3

    # 轻微平滑
    kernel_size = min(256, max(n // 20, 4))
    if kernel_size >= 2:
        kernel = np.ones(kernel_size) / kernel_size
        side = np.convolve(side, kernel, mode='same')

    left = mid + side
    right = mid - side
    return np.column_stack([left, right])


def process_effects(sig: np.ndarray, chain: EffectChain) -> np.ndarray:
    """应用完整效果链"""
    result = sig.copy()

    # 顺序: 滤波 → 失真 → 位压 → 混响 → 立体声
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
#  合成核心 (Synth Core)
# ============================================================
@dataclass
class SynthVoice:
    """单音合成参数"""
    freq: float = 440.0
    osc_type: OscType = OscType.SINE
    duration: float = 0.15            # 秒
    volume: float = 1.0
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional[EffectChain] = None
    pitch_mod: float = 0.0             # 音高变化量 (半音)
    vibrato_rate: float = 0.0          # 颤音频率 (Hz)
    vibrato_depth: float = 0.0         # 颤音深度 (半音)
    detune: float = 0.0                # 不协和度 (用于叠加音色)
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    # (倍频, 相对振幅) 泛音列表，如 [(2, 0.5), (3, 0.25)]


def synthesize_voice(voice: SynthVoice) -> np.ndarray:
    """合成单个声音"""
    n_samples = int(voice.duration * SR)
    if n_samples <= 0:
        n_samples = 1

    t = np.linspace(0, voice.duration, n_samples, dtype=np.float64)

    # 基础频率 + 微调
    base_freq = voice.freq * (2 ** (voice.pitch_mod / 12))

    # 颤音调制
    if voice.vibrato_depth > 0 and voice.vibrato_rate > 0:
        vib = 1.0 + (voice.vibrato_depth / 12) * np.sin(
            2 * np.pi * voice.vibrato_rate * t) * make_envelope(
            n_samples, EnvShape.PAD)[:n_samples]
        mod_freq = base_freq * vib
    else:
        mod_freq = base_freq
        vib = np.ones(n_samples)

    # 主振荡器
    main_sig = oscillator(t, mod_freq, voice.osc_type)

    # 泛音叠加
    for harmonic_mult, harmonic_amp in voice.harmonics:
        h_freq = mod_freq * harmonic_mult
        h_sig = oscillator(t, h_freq, voice.osc_type) * harmonic_amp
        main_sig += h_sig

    # 不协和叠加 (Unison)
    if abs(voice.detune) > 0.001:
        detune_sig = oscillator(
            t, mod_freq * (2 ** (voice.detune / 12)), voice.osc_type) * 0.6
        main_sig += detune_sig

    # 包络
    env = make_envelope(n_samples, voice.env_shape, voice.adsr)
    sig = main_sig * env * voice.volume

    # 效果链
    if voice.effect_chain is not None:
        sig = process_effects(sig, voice.effect_chain)

    # 安全限幅
    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak * 0.98

    return sig.astype(np.float32)


# ============================================================
#  SFX 音效预设库 (Sound Effects Presets)
# ============================================================

# ---------- UI 音效预设 ----------
UI_FX_PRESETS: Dict[str, SynthVoice] = {
    "button_click": SynthVoice(
        freq=800.0, osc_type=OscType.SQUARE, duration=0.06,
        volume=0.6, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(lp_filter_hz=4000, bit_crush=8),
        harmonics=[(1.5, 0.3)]
    ),
    "button_hover": SynthVoice(
        freq=1200.0, osc_type=OscType.SINE, duration=0.04,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=3,  # 上滑小三度
    ),
    "menu_open": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.25,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=7,  # 上滑纯五度
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.4),
    ),
    "menu_close": SynthVoice(
        freq=660.0, osc_type=OscType.SINE, duration=0.22,
        volume=0.45, env_shape=EnvShape.REVERSE,
        pitch_mod=-5,  # 下滑纯四度
    ),
    "confirm": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.2,
        volume=0.55, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.2)],
        effect_chain=EffectChain(reverb_mix=0.1),
    ),
    "cancel": SynthVoice(
        freq=330.0, osc_type=OscType.SAW, duration=0.18,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-4,
        effect_chain=EffectChain(lp_filter_hz=3000),
    ),
    "notification": SynthVoice(
        freq=880.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        vibrato_rate=6, vibrato_depth=2,
    ),
    "error": SynthVoice(
        freq=200.0, osc_type=OscType.SQUARE, duration=0.25,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-7,
        effect_chain=EffectChain(distortion=0.3, bit_crush=6),
        harmonics=[(1.5, 0.4), (2.0, 0.2)],
    ),
    "scroll": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.03,
        volume=0.25, env_shape=EnvShape.PERCUSSIVE,
    ),
}

# ---------- 卡牌音效预设 ----------
CARD_FX_PRESETS: Dict[str, SynthVoice] = {
    "card_play": SynthVoice(
        freq=520.0, osc_type=OscType.TRIANGLE, duration=0.18,
        volume=0.6, env_shape=EnvShape.PLUCK,
        pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.12),
        harmonics=[(2.0, 0.15), (3.0, 0.08)],
        detune=5,
    ),
    "card_draw": SynthVoice(
        freq=380.0, osc_type=OscType.SAW, duration=0.1,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-3,
        effect_chain=EffectChain(lp_filter_hz=5000, hp_filter_hz=150),
        harmonics=[(0.5, 0.2)],  # 加一个次八度
    ),
    "card_hover": SynthVoice(
        freq=900.0, osc_type=OscType.SINE, duration=0.035,
        volume=0.28, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
    ),
    "card_select": SynthVoice(
        freq=700.0, osc_type=OscType.TRIANGLE, duration=0.1,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=7,
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "shuffle": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_WHITE, duration=0.35,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=6000, hp_filter_hz=400,
            reverb_mix=0.1, reverb_decay=0.25,
        ),
    ),
    "card_reveal": SynthVoice(
        freq=350.0, osc_type=OscType.SINE, duration=0.4,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=12,  # 上滑一个八度
        harmonics=[(2.0, 0.2), (3.0, 0.08)],
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.5),
    ),
    "card_exhaust": SynthVoice(
        freq=250.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.4, env_shape=EnvShape.REVERSE,
        pitch_mod=-8,
        effect_chain=EffectChain(lp_filter_hz=3000, reverb_mix=0.12),
    ),
    "card_upgrade": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.5,
        volume=0.55, env_shape=EnvShape.SWELL,
        pitch_mod=12,
        vibrato_rate=5, vibrato_depth=2,
        harmonics=[(2.0, 0.25), (3.0, 0.1), (4.0, 0.05)],
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.6),
    ),
    "ethereal_pass": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.3,
        volume=0.4, env_shape=EnvShape.PAD,
        harmonics=[
            (2.0, 0.3), (3.0, 0.15), (4.0, 0.08), (5.0, 0.03)
        ],
        vibrato_rate=4.5, vibrato_depth=3,
        effect_chain=EffectChain(
            reverb_mix=0.3, reverb_decay=0.8,
            lp_filter_hz=5000, stereo_width=0.4,
        ),
    ),
}

# ---------- 战斗音效预设 ----------
COMBAT_FX_PRESETS: Dict[str, SynthVoice] = {
    "attack_melee": SynthVoice(
        freq=180.0, osc_type=OscType.NOISE_BROWN, duration=0.15,
        volume=0.75, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=2500, hp_filter_hz=80,
            distortion=0.4, bit_crush=8,
        ),
        harmonics=[(3.0, 0.3)],  # 叠加高频噪声
    ),
    "attack_magic": SynthVoice(
        freq=1200.0, osc_type=OscType.SAW, duration=0.35,
        volume=0.6, env_shape=EnvShape.SWELL,
        pitch_mod=-8,
        harmonics=[
            (1.5, 0.4), (2.0, 0.25), (2.5, 0.15), (3.33, 0.1)
        ],
        effect_chain=EffectChain(
            reverb_mix=0.25, reverb_decay=0.6,
            distortion=0.15,
        ),
    ),
    "block_hit": SynthVoice(
        freq=320.0, osc_type=OscType.SQUARE, duration=0.08,
        volume=0.65, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-6,
        effect_chain=EffectChain(
            lp_filter_hz=2000, distortion=0.25, bit_crush=10,
        ),
    ),
    "damage_taken": SynthVoice(
        freq=150.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.6, env_shape=EnvShape.REVERSE,
        pitch_mod=-12,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.15,
            distortion=0.2, stereo_width=0.3,
        ),
    ),
    "heal": SynthVoice(
        freq=523.25, osc_type=OscType.SINE, duration=0.5,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        vibrato_rate=5, vibrato_depth=2,
        effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.7),
    ),
    "dodge": SynthVoice(
        freq=2000.0, osc_type=OscType.NOISE_WHITE, duration=0.08,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=8000, hp_filter_hz=3000,
        ),
    ),
    "critical_hit": SynthVoice(
        freq=280.0, osc_type=OscType.NOISE_BROWN, duration=0.25,
        volume=0.8, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=3500, distortion=0.5, bit_crush=6,
            reverb_mix=0.15,
        ),
        harmonics=[(2.0, 0.3), (4.0, 0.15)],
    ),
    "enemy_death": SynthVoice(
        freq=200.0, osc_type=OscType.SAW, duration=0.6,
        volume=0.6, env_shape=EnvShape.REVERSE,
        pitch_mod=-16,
        effect_chain=EffectChain(
            lp_filter_hz=2500, reverb_mix=0.25, reverb_decay=1.0,
            distortion=0.2, stereo_width=0.5,
        ),
        harmonics=[(0.5, 0.3), (1.5, 0.2)],
    ),
    "player_hurt": SynthVoice(
        freq=100.0, osc_type=OscType.SQUARE, duration=0.2,
        volume=0.55, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-5,
        effect_chain=EffectChain(
            lp_filter_hz=1500, distortion=0.3, bit_crush=8,
        ),
    ),
    "shield_gain": SynthVoice(
        freq=450.0, osc_type=OscType.TRIANGLE, duration=0.25,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
        effect_chain=EffectChain(
            reverb_mix=0.12, lp_filter_hz=4000,
        ),
    ),
    "poison_tick": SynthVoice(
        freq=800.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-2,
        effect_chain=EffectChain(
            distortion=0.15, bit_crush=10,
            reverb_mix=0.08,
        ),
    ),
    "weak_hit": SynthVoice(
        freq=260.0, osc_type=OscType.NOISE_PINK, duration=0.07,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(
            lp_filter_hz=1800, hp_filter_hz=100,
        ),
    ),
}

# ---------- 系统音效预设 ----------
SYSTEM_FX_PRESETS: Dict[str, SynthVoice] = {
    "level_up": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.8,
        volume=0.6, env_shape=EnvShape.SWELL,
        harmonics=[(2.0, 0.3), (3.0, 0.15)],
        effect_chain=EffectChain(
            reverb_mix=0.2, reverb_decay=0.8,
            stereo_width=0.3,
        ),
    ),
    "achievement": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=1.0,
        volume=0.55, env_shape=EnvShape.SWELL,
        harmonics=[(1.5, 0.2), (2.0, 0.3), (2.5, 0.15), (3.0, 0.1), (4.0, 0.05)],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(
            reverb_mix=0.25, reverb_decay=1.0, stereo_width=0.4,
        ),
    ),
    "gold_pickup": SynthVoice(
        freq=988.0,  # B5
        osc_type=OscType.SINE, duration=0.12,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=2,
    ),
    "item_pickup": SynthVoice(
        freq=660.0, osc_type=OscType.TRIANGLE, duration=0.15,
        volume=0.45, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
        harmonics=[(2.0, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "potion_use": SynthVoice(
        freq=392.0,  # G4
        osc_type=OscType.SINE, duration=0.3,
        volume=0.48, env_shape=EnvShape.SWELL,
        pitch_mod=5,
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.5),
    ),
    "transition": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_PINK, duration=0.6,
        volume=0.35, env_shape=EnvShape.SWELL,
        effect_chain=EffectChain(
            lp_filter_hz=3000, reverb_mix=0.2, reverb_decay=0.8,
            stereo_width=0.5,
        ),
    ),
    "game_over": SynthVoice(
        freq=220.0, osc_type=OscType.SAW, duration=1.2,
        volume=0.5, env_shape=EnvShape.REVERSE,
        pitch_mod=-12,
        effect_chain=EffectChain(
            lp_filter_hz=2000, reverb_mix=0.3, reverb_decay=1.5,
            stereo_width=0.4,
        ),
    ),
    "victory_fanfare": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=1.5,
        volume=0.58, env_shape=EnvShape.SWELL,
        harmonics=[(1.5, 0.2), (2.0, 0.25), (2.5, 0.1)],
        effect_chain=EffectChain(
            reverb_mix=0.25, reverb_decay=1.2, stereo_width=0.5,
        ),
    ),
    "elite_alert": SynthVoice(
        freq=740.0,  # F#5
        osc_type=OscType.SQUARE, duration=0.3,
        volume=0.5, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=0,
        vibrato_rate=6, vibrato_depth=1.5,
        effect_chain=EffectChain(distortion=0.15, bit_crush=10),
    ),
    "boss_appear": SynthVoice(
        freq=100.0, osc_type=OscType.SAW, duration=1.0,
        volume=0.65, env_shape=EnvShape.SWELL,
        pitch_mod=-8,
        effect_chain=EffectChain(
            lp_filter_hz=1500, reverb_mix=0.3, reverb_decay=1.2,
            distortion=0.25, stereo_width=0.6, bit_crush=8,
        ),
        harmonics=[(0.5, 0.4), (2.0, 0.2)],
    ),
}


# ============================================================
#  音乐生成器 (Music Generator)
# ============================================================
@dataclass
class MusicPattern:
    """音乐模式数据"""
    name: str
    notes: List[Optional[str]]     # 音符名列表 (None=休止符)
    durations: List[float]         # 每个音符的时长 (拍)
    octave_shifts: List[int] = None  # 八度偏移列表
    bpm: int = 120
    loop: bool = True
    # 音色设置
    osc_type: OscType = OscType.SINE
    volume: float = 0.18
    env_shape: EnvShape = EnvShape.PAD
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    vibrato_rate: float = 0
    vibrato_depth: float = 0
    # 效果
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    stereo_width: float = 0.3
    lp_filter_hz: Optional[float] = None


def generate_music_wav(pattern: MusicPattern,
                       output_path: str,
                       duration_sec: Optional[float] = None) -> str:
    """
    将音乐模式生成为 WAV 文件
    Args:
        pattern: 音乐模式定义
        output_path: 输出文件路径
        duration_sec: 总时长(秒)，None 则根据模式自动计算
    Returns:
        输出的文件路径
    """
    beat_dur = 60.0 / pattern.bpm
    all_notes = []
    total_beats = sum(pattern.durations)

    # 如果指定了总时长，计算循环次数
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

    # 生成音频
    samples_list = []
    for note, dur, oct_v in all_notes:
        n_samp = int(dur * SR)
        t = np.linspace(0, dur, n_samp, dtype=np.float64)

        if note is None:
            sig = np.zeros(n_samp)
        else:
            f = note_to_freq(note) * (2 ** oct_v)
            sig = oscillator(t, f, pattern.osc_type)

            # 泛音
            for h_mult, h_amp in pattern.harmonics:
                sig += oscillator(t, f * h_mult, pattern.osc_type) * h_amp

            # 颤音
            if pattern.vibrato_depth > 0:
                vib_env = make_envelope(n_samp, EnvShape.PAD)
                vib = 1.0 + (pattern.vibrato_depth / 12) * np.sin(
                    2 * np.pi * pattern.vibrato_rate * t) * vib_env
                # 重做带颤音的振荡器
                sig = np.zeros(n_samp)
                mod_f = f * vib
                sig = oscillator(t, mod_f, pattern.osc_type)
                for h_mult, h_amp in pattern.harmonics:
                    sig += oscillator(t, mod_f * h_mult, pattern.osc_type) * h_amp

            # 包络
            env = make_envelope(n_samp, pattern.env_shape)
            sig = sig * env * pattern.volume

        samples_list.append(sig)

    # 拼接所有采样点
    full_signal = np.concatenate(samples_list) if samples_list else np.zeros(SR)

    # 效果处理
    chain = EffectChain(
        reverb_mix=pattern.reverb_mix,
        reverb_decay=pattern.reverb_decay,
        stereo_width=pattern.stereo_width,
        lp_filter_hz=pattern.lp_filter_hz,
    )
    processed = process_effects(full_signal, chain)

    # 确保是单声道 float32 用于写入
    if processed.ndim > 1 and processed.shape[1] >= 2:
        # 立体声 → 取均值回退为单声道 (或保持立体声)
        final = processed
    else:
        final = processed.reshape(-1, 1)

    # 写入 WAV
    final_int16 = np.clip(final * 32767, -32768, 32767).astype(np.int16)
    wavfile.write(output_path, SR, final_int16)

    return output_path


# ========== 音乐模式预设 ==========

# --- 菜单主题 (Menu Theme) ---
MENU_MUSIC = MusicPattern(
    name="menu_theme",
    notes=["C4", "Eb_4", "G4", "C5",
           "Bb4", "G4", "Eb_4", "C4",
           "Ab4", "C5", "Bb4", "G4",
           "Eb_4", "C4", None, "G4"],
    durations=[1.0, 0.5, 0.5, 1.0,
               0.5, 0.5, 1.0, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 1.0],
    octave_shifts=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    bpm=85,
    loop=True,
    osc_type=OscType.TRIANGLE,
    volume=0.16,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=4.5,
    vibrato_depth=1.5,
    reverb_mix=0.2,
    stereo_width=0.4,
    lp_filter_hz=4000,
)

# --- 低强度战斗音乐 (Battle Low Intensity) ---
BATTLE_LOW_MUSIC = MusicPattern(
    name="battle_low",
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
    volume=0.14,
    env_shape=EnvShape.PAD,
    harmonics=[(0.5, 0.15), (2.0, 0.1)],
    vibrato_rate=3,
    vibrato_depth=1,
    reverb_mix=0.15,
    stereo_width=0.3,
    lp_filter_hz=3000,
)

# --- 高强度战斗音乐 (Battle High Intensity) ---
BATTLE_HIGH_MUSIC = MusicPattern(
    name="battle_high",
    notes=["C3", "Eb3", "G3", "C4",
           "G3", "Eb3", "C3", "G2",
           "C3", "Eb3", "G3", "Bb3",
           "Ab3", "G3", "Eb3", "C3"],
    durations=[0.5, 0.5, 0.5, 0.5,
               0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5,
               0.75, 0.25, 0.5, 1.0],
    bpm=130,
    loop=True,
    osc_type=OscType.SAW,
    volume=0.17,
    env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5, 0.2), (2.0, 0.15), (3.0, 0.05)],
    reverb_mix=0.12,
    stereo_width=0.5,
    lp_filter_hz=4500,
)

# --- 事件/胜利音乐 (Event/Victory) ---
EVENT_MUSIC = MusicPattern(
    name="event_theme",
    notes=["C5", None, "E5", "G5",
           "C5", "B4", "C5", None,
           "G5", "E5", "C5", "B4",
           "C5", None, None, None],
    durations=[0.75, 0.25, 0.5, 0.5,
               0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5,
               1.0, 0.5, 1.0, 0.5],
    bpm=95,
    loop=True,
    osc_type=OscType.TRIANGLE,
    volume=0.18,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.25), (3.0, 0.1), (4.0, 0.03)],
    vibrato_rate=5,
    vibrato_depth=2,
    reverb_mix=0.25,
    stereo_width=0.5,
    lp_filter_hz=5000,
)

# --- 商人音乐 (Merchant) ---
MERCHANT_MUSIC = MusicPattern(
    name="merchant_theme",
    notes=["C4", "Eb4", "G4", "Eb4",
           "C4", "Bb3", "C4", None,
           "Eb4", "G4", "Bb4", "G4",
           "Eb4", "C4", None, None],
    durations=[0.66, 0.34, 0.5, 0.5,
               0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5,
               1.0, 0.5, 1.0, 0.5],
    bpm=100,
    loop=True,
    osc_type=OscType.SINE,
    volume=0.15,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.15), (3.0, 0.05), (5.0, 0.02)],
    vibrato_rate=5.5,
    vibrato_depth=1.5,
    reverb_mix=0.18,
    stereo_width=0.35,
)

# --- 休息/篝火音乐 (Campfire/Rest) ---
CAMPFIRE_MUSIC = MusicPattern(
    name="campfire_theme",
    notes=["G4", None, "E4", None,
           "C4", None, "E4", "G4",
           "A4", None, "E4", "C4",
           None, "D4", None, None],
    durations=[1.0, 0.5, 1.0, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 1.5, 0.5, 0.5],
    bpm=72,
    loop=True,
    osc_type=OscType.SINE,
    volume=0.14,
    env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.12), (3.0, 0.05)],
    vibrato_rate=3.5,
    vibrato_depth=1,
    reverb_mix=0.3,
    reverb_decay=1.2,
    stereo_width=0.5,
    lp_filter_hz=3500,
)

# 所有音乐模式汇总
ALL_MUSIC_PATTERNS: Dict[str, MusicPattern] = {
    "menu": MENU_MUSIC,
    "battle_low": BATTLE_LOW_MUSIC,
    "battle_high": BATTLE_HIGH_MUSIC,
    "event": EVENT_MUSIC,
    "merchant": MERCHANT_MUSIC,
    "campfire": CAMPFIRE_MUSIC,
}


# ============================================================
#  批量导出引擎 (Batch Export Engine)
# ============================================================
class AudioBatchExporter:
    """批量音频文件导出器"""

    def __init__(self, base_output_dir: str):
        self.base_dir = Path(base_output_dir)
        self.sfx_dir = self.base_dir / "sfx"
        self.music_dir = self.base_dir / "music"
        self.export_log: List[str] = []

    def ensure_dirs(self):
        """确保输出目录结构存在"""
        for cat in ["ui", "combat", "card", "system"]:
            (self.sfx_dir / cat).mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def export_sfx(self, preset_name: str, voice: SynthVoice,
                   category: str) -> str:
        """
        导出单个 SFX 为 WAV 文件
        Returns: 输出文件的绝对路径
        """
        sig = synthesize_voice(voice)
        filepath = self.sfx_dir / category / f"{preset_name}.wav"

        # 立体声检测
        if sig.ndim > 1 and sig.shape[1] >= 2:
            final = sig
        else:
            final = sig.reshape(-1, 1)

        wav_int = np.clip(final * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(str(filepath), SR, wav_int)

        log_msg = f"[SFX] {category}/{preset_name}.wav ({len(sig)/SR:.2f}s)"
        self.export_log.append(log_msg)
        print(f"  ✅ {log_msg}")
        return str(filepath)

    def export_all_sfx(self) -> Dict[str, str]:
        """导出所有 SFX 预设"""
        self.ensure_dirs()
        exported = {}

        categories = {
            "ui": UI_FX_PRESETS,
            "card": CARD_FX_PRESETS,
            "combat": COMBAT_FX_PRESETS,
            "system": SYSTEM_FX_PRESETS,
        }

        for cat, presets in categories.items():
            print(f"\n📦 生成 [{cat}] 音效 ({len(presets)} 个):")
            for name, voice in presets.items():
                path = self.export_sfx(name, voice, cat)
                exported[f"{cat}/{name}"] = path

        return exported

    def export_all_music(self, duration_sec: float = 30.0) -> Dict[str, str]:
        """导出所有音乐"""
        self.ensure_dirs()
        exported = {}

        print(f"\n🎵 生成音乐 ({duration_sec}s 每首):")
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            filepath = self.music_dir / f"{pattern.name}.wav"
            generate_music_wav(pattern, str(filepath), duration_sec=duration_sec)
            exported[key] = str(filepath)
            print(f"  ✅ [Music] {pattern.name}.wav")

        return exported

    def export_everything(self, music_duration: float = 30.0) -> Dict[str, str]:
        """一键导出全部音频资源"""
        print("=" * 55)
        print("  🎧 KARD 游戏音频批量生成器 v2.0")
        print("=" * 55)

        all_files = {}
        all_files.update(self.export_all_sfx())
        all_files.update(self.export_all_music(music_duration))

        total_sfx = sum(len(v) for v in [
            UI_FX_PRESETS, CARD_FX_PRESETS,
            COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
        ])
        total_music = len(ALL_MUSIC_PATTERNS)

        print(f"\n{'=' * 55}")
        print(f"  ✅ 完成! 共生成:")
        print(f"     • SFX 音效: {total_sfx} 个")
        print(f"     • 音乐:     {total_music} 首")
        print(f"     • 输出目录: {self.base_dir}")
        print(f"{'=' * 55}")

        return all_files


# ============================================================
#  实时预览播放器 (Real-time Preview Player)
# ============================================================
class PreviewPlayer:
    """实时音频预览 (使用 sounddevice 流)"""

    def __init__(self):
        self.current_stream: Optional[sd.OutputStream] = None
        self._audio_buffer: np.ndarray = np.array([])
        self._play_pos = int(0)
        self._is_playing = False
        self._lock = threading.Lock()
        self._loop = False

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if not self._is_playing or len(self._audio_buffer) == 0:
                outdata[:] = np.zeros((frames, 1), dtype=np.float32)
                return

            end_pos = self._play_pos + frames
            if end_pos >= len(self._audio_buffer):
                if self._loop:
                    remaining = frames - (len(self._audio_buffer) - self._play_pos)
                    tail = self._audio_buffer[self._play_pos:]
                    head = self._audio_buffer[:remaining]
                    chunk = np.concatenate([tail, head])
                    self._play_pos = remaining
                else:
                    chunk = self._audio_buffer[self._play_pos:self._play_pos + frames]
                    pad_needed = frames - len(chunk)
                    if pad_needed > 0:
                        chunk = np.pad(chunk, (0, pad_needed))
                    self._is_playing = False
                    self._play_pos = 0
            else:
                chunk = self._audio_buffer[self._play_pos:end_pos]
                self._play_pos = end_pos

            # 单声道/立体声适配
            if chunk.ndim == 1:
                outdata[:, 0] = chunk
            elif chunk.ndim == 2 and chunk.shape[1] == 1:
                outdata[:, 0] = chunk.flatten()
            elif chunk.ndim == 2 and chunk.shape[1] == 2:
                outdata[:, 0] = chunk[:, 0]  # 取左声道
            else:
                outdata[:, 0] = chunk.flatten()[:frames]

    def play(self, audio_data: np.ndarray, loop: bool = False):
        """播放音频数据"""
        self.stop()

        with self._lock:
            self._audio_buffer = audio_data.astype(np.float32)
            if self._audio_buffer.ndim == 0 or len(self._audio_buffer) == 0:
                return
            if self._audio_buffer.ndim == 2 and self._audio_buffer.shape[1] >= 2:
                self._audio_buffer = self._audio_buffer[:, 0]  # 取左声道预览
            self._play_pos = 0
            self._is_playing = True
            self._loop = loop

        try:
            self.current_stream = sd.OutputStream(
                samplerate=SR,
                channels=1,
                dtype='float32',
                callback=self._callback,
                blocksize=1024,
                latency='low',
            )
            self.current_stream.start()
        except Exception as e:
            print(f"⚠️ 音频设备错误: {e}")
            self._is_playing = False

    def stop(self):
        """停止播放"""
        with self._lock:
            self._is_playing = False
        if self.current_stream is not None:
            try:
                self.current_stream.stop()
                self.current_stream.close()
            except Exception:
                pass
            self.current_stream = None

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing


# ============================================================
#  GUI 工作站界面 (Audio Workstation GUI)
# ============================================================
class GameAudioWorkstationGUI:
    """KARD 游戏音频工作站图形界面"""

    # 配色方案
    BG_COLOR = "#1a1a2e"
    FG_COLOR = "#eee"
    ACCENT_COLOR = "#e94560"
    PANEL_COLOR = "#16213e"
    SUCCESS_COLOR = "#0f9d58"
    WARNING_COLOR = "#f1c40f"
    TEXT_MONO = ("Consolas", 9)

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎧 KARD 游戏音频制作工作站 v2.0")
        self.root.geometry("920x680")
        self.root.configure(bg=self.BG_COLOR)
        self.root.minsize(800, 550)

        # 核心
        self.player = PreviewPlayer()
        self.exporter: Optional[AudioBatchExporter] = None
        self.output_dir = tk.StringVar(value=r"C:\Users\13122\Desktop\stay\kard_CN\assets\audio")

        # 当前选中项
        self.selected_preset: Optional[tuple] = None  # (category, name, voice)

        self._build_ui()

    def _build_ui(self):
        """构建全部 UI 元素"""
        # ===== 顶部工具栏 =====
        toolbar = ttk.Frame(self.root, padding=(8, 4))
        toolbar.pack(fill=tk.X)

        tk.Label(toolbar, text="📁 输出目录:", bg=self.BG_COLOR,
                 fg=self.FG_COLOR, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Entry(toolbar, textvariable=self.output_dir, width=55,
                 font=("Consolas", 8)).pack(side=tk.LEFT, padx=(4, 8))
        tk.Button(toolbar, text="🔊 批量生成全部", command=self._on_batch_export,
                  bg=self.ACCENT_COLOR, fg="white", font=("Arial", 9, "bold"),
                  padx=12).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="▶️ 预览选中", command=self._on_preview_selected,
                  bg=self.SUCCESS_COLOR, fg="white",
                  font=("Arial", 9)).pack(side=tk.LEFT, padx=2)

        # ===== 主区域：左右分栏 =====
        main_pane = tk.Frame(self.root, bg=self.BG_COLOR)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左侧: SFX 列表
        left_frame = tk.LabelFrame(main_pane, text=" 🔊 SFX 音效预设 ",
                                   bg=self.BG_COLOR, fg=self.ACCENT_COLOR,
                                   font=("Arial", 10, "bold"), padx=4, pady=4)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        # SFX Treeview
        columns = ("type", "dur", "osc")
        self.sfx_tree = ttk.Treeview(left_frame, columns=columns,
                                      show="tree headings", height=18,
                                      selectmode="browse")
        self.sfx_tree.heading("#0", text="名称")
        self.sfx_tree.heading("type", text="波形")
        self.sfx_tree.heading("dur", text="时长(s)")
        self.sfx_tree.heading("osc", text="包络")
        self.sfx_tree.column("#0", width=160)
        self.sfx_tree.column("type", width=80)
        self.sfx_tree.column("dur", width=60)
        self.sfx_tree.column("osc", width=90)

        scrollbar_y = ttk.Scrollbar(left_frame, orient=tk.VERTICAL,
                                     command=self.sfx_tree.yview)
        self.sfx_tree.configure(yscrollcommand=scrollbar_y.set)

        self.sfx_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.sfx_tree.bind("<<TreeviewSelect>>", self._on_select_preset)
        self.sfx_tree.bind("<Double-1>", lambda _: self._on_preview_selected())

        self._populate_sfx_tree()

        # 右侧面板: 详情 + 音乐 + 日志
        right_frame = tk.Frame(main_pane, bg=self.BG_COLOR)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

        # --- 预设详情 ---
        detail_labelframe = tk.LabelFrame(right_frame, text=" 🎛️ 预设详情 ",
                                          bg=self.BG_COLOR, fg=self.WARNING_COLOR,
                                          font=("Arial", 10, "bold"))
        detail_labelframe.pack(fill=tk.X, pady=(0, 4))

        self.detail_text = tk.Text(detail_labelframe, height=10, wrap=tk.WORD,
                                   bg="#0d1117", fg="#58a6ff",
                                   font=("Consolas", 9), state=tk.DISABLED,
                                   insertbackground="#58a6ff")
        self.detail_text.pack(fill=tk.X, padx=4, pady=4)

        # --- 音乐列表 ---
        music_lf = tk.LabelFrame(right_frame, text=" 🎵 音乐预设 ",
                                 bg=self.BG_COLOR, fg=self.SUCCESS_COLOR,
                                 font=("Arial", 10, "bold"))
        music_lf.pack(fill=tk.X, pady=(0, 4))

        music_btn_frame = tk.Frame(music_lf, bg=self.BG_COLOR)
        music_btn_frame.pack(fill=tk.X, padx=4, pady=4)

        for key, pattern in ALL_MUSIC_PATTERNS.items():
            color = {
                "menu": "#3498db", "battle_low": "#e74c3c",
                "battle_high": "#c0392b", "event": "#2ecc71",
                "merchant": "#f39c12", "campfire": "#1abc9c",
            }.get(key, "#888")
            btn = tk.Button(music_btn_frame, text=pattern.name,
                            bg=color, fg="white", font=("Arial", 8),
                            width=11, padx=4, pady=2,
                            command=lambda k=key: self._on_preview_music(k))
            btn.pack(side=tk.LEFT, padx=2, pady=2)

        ctrl_frame = tk.Frame(music_lf, bg=self.BG_COLOR)
        ctrl_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(ctrl_frame, text="音乐长度:", bg=self.BG_COLOR,
                 fg=self.FG_COLOR, font=("Arial", 9)).pack(side=tk.LEFT)
        self.music_duration_var = tk.StringVar(value="15")
        tk.Entry(ctrl_frame, textvariable=self.music_duration_var, width=5,
                 font=("Consolas", 9)).pack(side=tk.LEFT, padx=(2, 8))
        tk.Button(ctrl_frame, text="🎼 导出全部音乐",
                  command=self._on_export_music,
                  bg=self.SUCCESS_COLOR, fg="white",
                  font=("Arial", 9)).pack(side=tk.LEFT)

        # --- 日志输出 ---
        log_lf = tk.LabelFrame(right_frame, text=" 📋 输出日志 ",
                               bg=self.BG_COLOR, fg="#aaa",
                               font=("Arial", 10, "bold"))
        log_lf.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_lf, height=10, wrap=tk.WORD,
            bg="#0d1117", fg="#8b949e",
            font=("Consolas", 8), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ===== 底部状态栏 =====
        statusbar = tk.Frame(self.root, bg=self.PANEL_COLOR, height=24)
        statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(statusbar,
                                     text="✅ 就绪 — 选择左侧音效进行预览，或点击「批量生成」",
                                     bg=self.PANEL_COLOR, fg=self.FG_COLOR,
                                     font=("Arial", 9), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=8)

    def _populate_sfx_tree(self):
        """填充 SFX 树形列表"""
        categories = {
            "🖥️ UI": ("ui", UI_FX_PRESETS),
            "🃏 卡牌": ("card", CARD_FX_PRESETS),
            "⚔️ 战斗": ("combat", COMBAT_FX_PRESETS),
            "⚙️ 系统": ("system", SYSTEM_FX_PRESETS),
        }

        for cat_label, (cat_key, presets) in categories.items():
            parent_id = self.sfx_tree.insert("", "end", text=cat_label,
                                              values=("", "", ""), open=True)
            for name, voice in presets.items():
                osc_map = {
                    OscType.SINE: "正弦", OscType.SQUARE: "方波",
                    OscType.SAW: "锯齿", OscType.TRIANGLE: "三角",
                    OscType.NOISE_WHITE: "白噪声",
                    OscType.NOISE_PINK: "粉噪声",
                    OscType.NOISE_BROWN: "棕噪声",
                }
                env_map = {
                    EnvShape.PERCUSSIVE: "打击", EnvShape.PAD: "铺底",
                    EnvShape.PLUCK: "弹拨", EnvShape.SWELL: "渐变",
                    EnvShape.REVERSE: "反向",
                }
                self.sfx_tree.insert(parent_id, "end",
                                     text=name,
                                     values=(
                                         osc_map.get(voice.osc_type, "?"),
                                         f"{voice.duration:.2f}",
                                         env_map.get(voice.env_shape, "?"),
                                     ),
                                     tags=(cat_key, name))

    def _on_select_preset(self, event=None):
        """选中预设时显示详情"""
        sel = self.sfx_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        values = self.sfx_tree.item(item_id)
        name = values["text"]
        tags = values.get("tags", ("unknown", ""))

        if len(tags) != 2 or not tags[1]:
            return

        category, preset_name = tags

        # 查找对应 Voice
        all_presets = {
            **{f"ui/{k}": v for k, v in UI_FX_PRESETS.items()},
            **{f"card/{k}": v for k, v in CARD_FX_PRESETS.items()},
            **{f"combat/{k}": v for k, v in COMBAT_FX_PRESETS.items()},
            **{f"system/{k}": v for k, v in SYSTEM_FX_PRESETS.items()},
        }

        key = f"{category}/{preset_name}"
        voice = all_presets.get(key)
        if voice is None:
            return

        self.selected_preset = (category, preset_name, voice)

        # 显示详情文本
        info_lines = [
            f"┌─ {'='*42}",
            f"│  预设: {preset_name}",
            f"│  分类: {category.upper()}",
            f"├─ {'='*42}",
            f"│  频率:     {voice.freq:.1f} Hz",
            f"│  波形:     {voice.osc_type.value}",
            f"│  时长:     {voice.duration:.3f} s",
            f"│  音量:     {voice.volume:.2f}",
            f"│  包络:     {voice.env_shape.value}",
            "",
        ]

        if voice.adsr:
            info_lines.append(f"│  ADSR:     A={voice.adsr.attack:.3f} "
                             f"D={voice.adsr.decay:.3f} "
                             f"S={voice.adsr.sustain:.2f} "
                             f"R={voice.adsr.release:.3f}")
        if voice.pitch_mod != 0:
            info_lines.append(f"│  音高偏移: ±{abs(voice.pitch_mod):.1f} 半音 "
                             f"({'上滑' if voice.pitch_mod > 0 else '下滑'})")
        if voice.vibrato_depth > 0:
            info_lines.append(f"│  颤音:     rate={voice.vibrato_rate:.1f}Hz "
                             f"depth={voice.vibrato_depth:.1f}半音")
        if voice.detune != 0:
            info_lines.append(f"│  不协和:   ±{voice.detune:.1f} 半音")
        if voice.harmonics:
            h_str = ", ".join([f"x{h[0]}({h[1]:.0%})" for h in voice.harmonics])
            info_lines.append(f"│  泛音:     [{h_str}]")
        if voice.effect_chain:
            ec = voice.effect_chain
            info_lines.append("")
            info_lines.append("│  ── 效果链 ──")
            if ec.lp_filter_hz:
                info_lines.append(f"│  低通滤波: {ec.lp_filter_hz:.0f} Hz")
            if ec.hp_filter_hz:
                info_lines.append(f"│  高通滤波: {ec.hp_filter_hz:.0f} Hz")
            if ec.distortion > 0:
                info_lines.append(f"│  失真:     {ec.distortion:.0%}")
            if ec.bit_crush < 16:
                info_lines.append(f"│  位压缩:   {ec.bit_crush}-bit")
            if ec.reverb_mix > 0:
                info_lines.append(f"│  混响:     mix={ec.reverb_mix:.0%} "
                                 f"decay={ec.reverb_decay:.1f}s")
            if ec.stereo_width > 0:
                info_lines.append(f"│  立体声:   width={ec.stereo_width:.0%}")

        info_lines.append(f"└─ {'='*42}")

        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "\n".join(info_lines))
        self.detail_text.config(state=tk.DISABLED)

    def _on_preview_selected(self):
        """预览选中的 SFX"""
        if self.selected_preset is None:
            self._log("❌ 请先选择一个音效预设")
            return

        _, _, voice = self.selected_preset
        sig = synthesize_voice(voice)
        self.player.play(sig)
        self._log(f"▶️ 正在预览: {self.selected_preset[1]}")

    def _on_preview_music(self, key: str):
        """预览音乐 (写入临时 WAV 文件再播放)"""
        import tempfile, soundfile as sf
        pattern = ALL_MUSIC_PATTERNS.get(key)
        if pattern is None:
            return

        # 生成音频数据
        buf = io.BytesIO()
        generate_music_wav(pattern, buf, duration_sec=8.0)
        buf.seek(0)
        sr_, data = wavfile.read(buf)
        if data.dtype == np.int16:
            sig = data.astype(np.float32) / 32768.0
        else:
            sig = data.astype(np.float32)
        # 截取前 8 秒
        max_samples = int(8 * SR)
        if len(sig) > max_samples:
            sig = sig[:max_samples]
        self.player.play(sig, loop=False)
        self._log(f"▶️ 正在预览音乐: {pattern.name}")

    def _on_batch_export(self):
        """批量导出所有音频"""
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showerror("错误", "请先设置输出目录!")
            return

        self.exporter = AudioBatchExporter(out_dir)
        self._log(f"🚀 开始批量导出到: {out_dir}\n")

        def do_export():
            try:
                files = self.exporter.export_everything(music_duration=float(
                    self.music_duration_var.get()))
                self._log(f"\n✅ 批量生成完成! 共 {len(files)} 个文件\n")
                self._status(f"✅ 已生成 {len(files)} 个音频文件 → {out_dir}")
                messagebox.showinfo("完成",
                                    f"成功生成 {len(files)} 个音频文件!\n"
                                    f"位置: {out_dir}")
            except Exception as e:
                self._log(f"\n❌ 导出失败: {e}\n")
                messagebox.showerror("错误", f"导出失败:\n{e}")

        # 在后台线程执行以避免阻塞 GUI
        thread = threading.Thread(target=do_export, daemon=True)
        thread.start()

    def _on_export_music(self):
        """仅导出音乐"""
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            return
        exporter = AudioBatchExporter(out_dir)
        exporter.ensure_dirs()
        dur = float(self.music_duration_var.get())

        def do_it():
            try:
                exporter.export_all_music(duration_sec=dur)
                self._log(f"✅ 音乐已导出 ({dur}s/首)")
            except Exception as e:
                self._log(f"❌ 音乐导出失败: {e}")

        thread = threading.Thread(target=do_it, daemon=True)
        thread.start()

    def _log(self, msg: str):
        """追加日志"""
        self.log_text.config(state=tk.NORMAL)
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _status(self, msg: str):
        """更新状态栏"""
        self.status_label.config(text=msg)


# ============================================================
#  CLI 批量导出模式
# ============================================================
def cli_batch_export(output_dir: str, music_duration: float = 30.0):
    """命令行批量导出模式 (无 GUI)"""
    exporter = AudioBatchExporter(output_dir)
    exporter.export_everything(music_duration=music_duration)


# ============================================================
#  入口点
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KARD 游戏音频制作工作站")
    parser.add_argument("--batch", action="store_true",
                        help="CLI 批量导出模式 (不启动GUI)")
    parser.add_argument("--output", "-o", type=str,
                        default=r"C:\Users\13122\Desktop\stay\kard_CN\assets\audio",
                        help="输出根目录")
    parser.add_argument("--duration", "-d", type=float, default=30.0,
                        help="每首音乐的时长(秒)")
    parser.add_argument("--preview", type=str, default=None,
                        help="预览指定SFX名称 (如 ui/button_click)")

    args = parser.parse_args()

    if args.preview:
        # 预览模式
        all_presets = {
            **{f"ui/{k}": v for k, v in UI_FX_PRESETS.items()},
            **{f"card/{k}": v for k, v in CARD_FX_PRESETS.items()},
            **{f"combat/{k}": v for k, v in COMBAT_FX_PRESETS.items()},
            **{f"system/{k}": v for k, v in SYSTEM_FX_PRESETS.items()},
        }
        voice = all_presets.get(args.preview)
        if voice:
            sig = synthesize_voice(voice)
            player = PreviewPlayer()
            player.play(sig)
            print(f"▶️ 正在预览: {args.preview} ({len(sig)/SR:.2f}s)")
            input("按 Enter 停止...")
            player.stop()
        else:
            print(f"❌ 未找到预设: {args.preview}")
            print(f"可用预设: {list(all_presets.keys())}")
    elif args.batch:
        # 批量导出模式
        print(f"🚀 CLI 批量导出模式 → {args.output}")
        cli_batch_export(args.output, args.duration)
    else:
        # GUI 模式
        root = tk.Tk()
        app = GameAudioWorkstationGUI(root)

        # 窗口关闭清理
        def on_closing():
            app.player.stop()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
