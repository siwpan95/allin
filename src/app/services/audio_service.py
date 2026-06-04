# -*- coding: utf-8 -*-
"""
音频服务 — 实时播放 / 音量控制 / 批量导出接口

合成引擎和预设库已拆分到 audio_engine.py / audio_presets.py。
"""

import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

#  尝试导入 sounddevice；缺失时自动禁用实时播放
try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False
    sd = None

#  从合成引擎导入
from .audio_engine import (
    SR, SynthVoice, synthesize_voice,
    process_effects, EffectChain,
    MusicPattern, generate_music_wav,
)
#  从预设库导入
from .audio_presets import (
    ALL_SFX_PRESETS, ALL_MUSIC_PATTERNS,
)


VOL_SFX = 0.8
VOL_MUSIC = 0.6


# ============================================================
#  实时播放器 (sounddevice 流式播放)
# ============================================================
class _AudioPlayer:
    """轻量级音频实时播放器 (sounddevice 流式播放)"""

    def __init__(self):
        self._stream = None
        self._buffer: np.ndarray = np.array([])
        self._pos = int(0)
        self._playing = False
        self._loop = False
        self._lock = threading.Lock()

    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if not self._playing or len(self._buffer) == 0:
                outdata[:] = np.zeros((frames, 1), dtype=np.float32)
                return

            end_pos = self._pos + frames
            if end_pos >= len(self._buffer):
                if self._loop:
                    remaining = frames - (len(self._buffer) - self._pos)
                    chunk = np.concatenate([
                        self._buffer[self._pos:],
                        self._buffer[:remaining],
                    ])
                    self._pos = remaining
                else:
                    chunk = self._buffer[self._pos:self._pos + frames]
                    pad_needed = frames - len(chunk)
                    if pad_needed > 0:
                        chunk = np.pad(chunk, (0, pad_needed))
                    self._playing = False
                    self._pos = 0
            else:
                chunk = self._buffer[self._pos:end_pos]
                self._pos = end_pos

            if chunk.ndim == 1:
                outdata[:, 0] = chunk
            elif chunk.ndim == 2 and chunk.shape[1] == 1:
                outdata[:, 0] = chunk.flatten()
            elif chunk.ndim == 2 and chunk.shape[1] == 2:
                outdata[:, 0] = chunk[:, 0]
            else:
                outdata[:, 0] = chunk.flatten()[:frames]

    def play(self, audio_data: np.ndarray, loop: bool = False):
        if not _SD_AVAILABLE:
            return
        self.stop()

        with self._lock:
            self._buffer = audio_data.astype(np.float32)
            if self._buffer.ndim == 0 or len(self._buffer) == 0:
                return
            if self._buffer.ndim == 2 and self._buffer.shape[1] >= 2:
                self._buffer = self._buffer[:, 0]
            self._pos = 0
            self._playing = True
            self._loop = loop

        try:
            self._stream = sd.OutputStream(
                samplerate=SR, channels=1, dtype='float32',
                callback=self._callback, blocksize=1024, latency='low',
            )
            self._stream.start()
        except Exception:
            self._playing = False

    def stop(self):
        with self._lock:
            self._playing = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._playing


# ============================================================
#  音频服务主类
# ============================================================
class AudioService:
    """
    蜂蜜挂机 RPG 音频服务

    提供统一的音效/音乐播放接口，内部管理：
      - SFX 预设查找与合成
      - 音乐模式切换与循环播放
      - WAV 批量导出
      - 全局音量与开关控制
    """

    def __init__(self, enabled: bool = True, sfx_volume: float = 1.0,
                 music_volume: float = 1.0):
        self.enabled = enabled and _SD_AVAILABLE
        self.sfx_volume = sfx_volume
        self.music_volume = music_volume
        self._player = _AudioPlayer()
        self._music_player = _AudioPlayer()
        self._current_music_key: Optional[str] = None
        self._cooldown_timer: float = 0.0
        self._cooldown_interval: float = 0.05  # SFX 最小间隔，防止堆叠
        # 防抖: 同一 SFX 的最短重复间隔
        self._last_played: Dict[str, float] = {}
        self._debounce: Dict[str, float] = {
            "combat/attack_melee": 0.3,
            "combat/damage_taken": 0.5,
            "system/gold_gain": 0.15,
            "system/exp_gain": 0.15,
            "system/farm_income": 0.5,
        }

    # ---- 核心播放接口 ----

    def play_sfx(self, key: str, volume_scale: float = 1.0) -> bool:
        """
        播放指定 SFX 音效

        Args:
            key: 音效标识，格式 "category/name"，如 "combat/attack_melee"
            volume_scale: 额外音量缩放 (0-1)
        Returns:
            是否成功触发播放
        """
        if not self.enabled:
            return False

        voice = self._resolve_preset(key)
        if voice is None:
            return False

        # 冷却检查
        now = time.time()
        if now - self._cooldown_timer < self._cooldown_interval:
            return False
        # 防抖检查
        debounce_time = self._debounce.get(key, 0.0)
        last = self._last_played.get(key, 0.0)
        if now - last < debounce_time:
            return False

        sig = synthesize_voice(voice)
        if self.sfx_volume != 1.0 or volume_scale != 1.0:
            sig = sig * self.sfx_volume * volume_scale
        self._player.play(sig)
        self._cooldown_timer = now
        self._last_played[key] = now
        return True

    def play_music(self, key: str, loop: bool = True) -> bool:
        """
        播放背景音乐

        Args:
            key: 音乐名称，如 "exploration", "battle", "town"
            loop: 是否循环播放
        Returns:
            是否成功触发播放
        """
        if not self.enabled:
            return False
        if key == self._current_music_key and self._music_player.is_playing:
            return False

        pattern = ALL_MUSIC_PATTERNS.get(key)
        if pattern is None:
            return False

        from .audio_engine import generate_music_wav
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), f"bee_rpg_music_{key}.wav")
        generate_music_wav(pattern, tmp, duration_sec=60.0)
        from scipy import wavfile
        sr, data = wavfile.read(tmp)
        if data.dtype == np.int16:
            sig = data.astype(np.float32) / 32768.0
        else:
            sig = data.astype(np.float32)
        if self.music_volume != 1.0:
            sig = sig * self.music_volume
        self._music_player.play(sig, loop=loop)
        self._current_music_key = key
        return True

    def stop_music(self):
        self._music_player.stop()
        self._current_music_key = None

    def stop_all(self):
        self._player.stop()
        self._music_player.stop()
        self._current_music_key = None

    # ---- 快捷音效方法 (供 GameController 直接调用) ----

    def sfx_combat_attack(self):       return self.play_sfx("combat/attack_melee")
    def sfx_combat_magic(self):        return self.play_sfx("combat/attack_magic")
    def sfx_combat_critical(self):     return self.play_sfx("combat/critical_hit")
    def sfx_combat_block(self):        return self.play_sfx("combat/block_hit")
    def sfx_combat_hurt(self):         return self.play_sfx("combat/damage_taken")
    def sfx_combat_dodge(self):        return self.play_sfx("combat/dodge")
    def sfx_combat_heal(self):         return self.play_sfx("combat/heal")
    def sfx_combat_enemy_death(self):  return self.play_sfx("combat/enemy_death")
    def sfx_combat_player_hurt(self):   return self.play_sfx("combat/player_hurt_serious")
    def sfx_combat_shield(self):       return self.play_sfx("combat/shield_gain")
    def sfx_combat_poison(self):       return self.play_sfx("combat/poison_tick")

    def sfx_explore_dungeon_enter(self):   return self.play_sfx("exploration/dungeon_enter")
    def sfx_explore_room_clear(self):     return self.play_sfx("exploration/room_clear")
    def sfx_explore_chest(self):         return self.play_sfx("exploration/chest_open")
    def sfx_explore_loot(self):          return self.play_sfx("exploration/loot_pickup")
    def sfx_explore_equip(self):         return self.play_sfx("exploration/item_equip")
    def sfx_explore_landmark(self):      return self.play_sfx("exploration/landmark_discover")
    def sfx_explore_potion(self):        return self.play_sfx("exploration/potion_pickup")
    def sfx_explore_travel(self):        return self.play_sfx("exploration/travel_region")
    def sfx_explore_elite(self):         return self.play_sfx("exploration/elite_alert")
    def sfx_explore_dungeon_cleared(self): return self.play_sfx("exploration/dungeon_cleared")
    def sfx_explore_infestation(self):   return self.play_sfx("exploration/infestation_warning")

    def sfx_system_levelup(self):      return self.play_sfx("system/level_up")
    def sfx_system_achievement(self): return self.play_sfx("system/achievement_unlock")
    def sfx_system_gold(self):        return self.play_sfx("system/gold_gain")
    def sfx_system_exp(self):         return self.play_sfx("system/exp_gain")
    def sfx_system_resurrect(self):   return self.play_sfx("system/member_resurrect")
    def sfx_system_fallen(self):     return self.play_sfx("system/member_fallen")
    def sfx_system_quest(self):      return self.play_sfx("system/quest_complete")
    def sfx_system_artifact(self):   return self.play_sfx("system/artifact_found")
    def sfx_system_castle(self):     return self.play_sfx("system/castle_built")
    def sfx_system_farm(self):       return self.play_sfx("system/farm_income")

    def sfx_ui_click(self): return self.play_sfx("ui/button_click")
    def sfx_ui_save(self):   return self.play_sfx("ui/save_complete")

    # ---- 内部方法 ----

    def _resolve_preset(self, key: str) -> Optional[SynthVoice]:
        """根据 'category/name' 键解析预设声音"""
        parts = key.split("/")
        if len(parts) != 2:
            return None
        cat, name = parts[0], parts[1]
        preset_cat = ALL_SFX_PRESETS.get(cat)
        if preset_cat is None:
            return None
        return preset_cat.get(name)

    def _generate_music_signal(self, pattern: MusicPattern,
                              duration_sec: Optional[float] = None) -> np.ndarray:
        """将 MusicPattern 合成为 numpy 信号数组 (不写文件)"""
        import tempfile, os
        from scipy import wavfile
        tmp = os.path.join(tempfile.gettempdir(), "bee_rpg_music_tmp.wav")
        generate_music_wav(pattern, tmp, duration_sec=duration_sec)
        sr, data = wavfile.read(tmp)
        if data.dtype == np.int16:
            sig = data.astype(np.float32) / 32768.0
        else:
            sig = data.astype(np.float32)
        return sig

    # ---- 批量导出 ----

    def export_all(self, output_dir: str, music_duration: float = 30.0) -> Dict[str, str]:
        """
        导出所有音频资源到指定目录

        目录结构:
          output_dir/
          ├── sfx/
          │   ├── ui/
          │   ├── combat/
          │   ├── exploration/
          │   └── system/
          └── music/
        Returns:
          {相对路径: 绝对路径} 映射字典
        """
        exporter = _AudioBatchExporter(output_dir)
        return exporter.export_everything(music_duration=music_duration)

    @staticmethod
    def list_all_sfx() -> List[str]:
        """列出所有可用的 SFX 标识"""
        keys = []
        for cat, presets in ALL_SFX_PRESETS.items():
            for name in presets:
                keys.append(f"{cat}/{name}")
        return sorted(keys)

    @staticmethod
    def list_all_music() -> List[str]:
        """列出所有可用的音乐名称"""
        return list(ALL_MUSIC_PATTERNS.keys())

    @property
    def available(self) -> bool:
        """音频系统是否可用 (sounddevice 已安装)"""
        return _SD_AVAILABLE

    def set_volume(self, sfx: Optional[float] = None, music: Optional[float] = None):
        """设置音量 (0.0-1.0)"""
        if sfx is not None:
            self.sfx_volume = max(0.0, min(1.0, sfx))
        if music is not None:
            self.music_volume = max(0.0, min(1.0, music))


# ============================================================
#  批量导出器 (内部使用)
# ============================================================
class _AudioBatchExporter:
    """批量导出器"""

    def __init__(self, base_output_dir: str):
        from pathlib import Path
        self.base_dir = Path(base_output_dir)
        self.sfx_dir = self.base_dir / "sfx"
        self.music_dir = self.base_dir / "music"

    def ensure_dirs(self):
        for cat in ["ui", "combat", "exploration", "system"]:
            (self.sfx_dir / cat).mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def export_sfx(self, preset_name: str, voice: SynthVoice,
                   category: str) -> str:
        import numpy as np
        from scipy import wavfile
        sig = synthesize_voice(voice)
        filepath = self.sfx_dir / category / f"{preset_name}.wav"
        if sig.ndim > 1 and sig.shape[1] >= 2:
            final = sig
        else:
            final = sig.reshape(-1, 1)
        wav_int = np.clip(final * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(str(filepath), SR, wav_int)
        print(f"  [SFX] {category}/{preset_name}.wav ({len(sig)/SR:.2f}s)")
        return str(filepath)

    def export_all_sfx(self) -> Dict[str, str]:
        self.ensure_dirs()
        exported = {}
        for cat, presets in ALL_SFX_PRESETS.items():
            print(f"\n  [{cat}] 音效 ({len(presets)} 个):")
            for name, voice in presets.items():
                path = self.export_sfx(name, voice, cat)
                exported[f"{cat}/{name}"] = path
        return exported

    def export_all_music(self, duration_sec: float = 30.0) -> Dict[str, str]:
        self.ensure_dirs()
        exported = {}
        print(f"\n  音乐 ({duration_sec}s/首):")
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            filepath = self.music_dir / f"{pattern.name}.wav"
            generate_music_wav(pattern, str(filepath), duration_sec=duration_sec)
            exported[key] = str(filepath)
            print(f"  [Music] {pattern.name}.wav")
        return exported

    def export_everything(self, music_duration: float = 30.0) -> Dict[str, str]:
        print("=" * 55)
        print("  🎧 蜂蜜挂机 RPG — 音频批量生成")
        print("=" * 55)

        all_files = {}
        all_files.update(self.export_all_sfx())
        all_files.update(self.export_all_music(music_duration))

        total_sfx = sum(len(v) for v in ALL_SFX_PRESETS.values())
        total_music = len(ALL_MUSIC_PATTERNS)
        print(f"\n{'=' * 55}")
        print(f"  完成! 共生成:")
        print(f"    SFX 音效: {total_sfx} 个")
        print(f"    音乐:     {total_music} 首")
        print(f"    输出目录: {self.base_dir}")
        print(f"{'=' * 55}")

        return all_files
