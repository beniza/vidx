"""
Configuration Module for VIDX
Loads, validates, and manages defaults for YAML configuration files.
"""
import os
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "project": {
        "name": "Scripture Video Project",
        "output_dir": "output"
    },
    "video": {
        "resolution": "1920x1080",
        "fps": 24,
        "codec": "libx264",
        "preset": "fast",
        "crf": 23,
        "background_media": "",
        "loop_background": True,
        "scaling_mode": "pad"  # 'pad' (maintain aspect ratio with padding), 'crop' (fill screen), 'stretch'
    },
    "audio": {
        "codec": "aac",
        "bitrate": "192k",
        "sample_rate": 48000
    },
    "style": {
        "verse": {
            "font": "Nirmala UI",
            "size": 48,
            "color": "#FFFFFF",
            "outline_color": "#000000",
            "outline_width": 3,
            "shadow": 1,
            "alignment": 2,  # 2 = bottom center
            "margin_bottom": 60,
            "margin_lr": 60,
            "background_box": True,
            "background_color": "#00000080"
        },
        "heading": {
            "font": "Nirmala UI",
            "size": 56,
            "color": "#FFD400",
            "outline_color": "#000000",
            "outline_width": 3,
            "shadow": 1,
            "alignment": 8,  # 8 = top center
            "margin_vertical": 80,
            "bold": True,
            "background_box": True,
            "background_color": "#00000080"
        },
        "verse_number": {
            "show": True,
            "color": "#FFC080",
            "size": 36,
            "on_every_segment": False
        }
    }
}


def merge_dict(base, override):
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_dict(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    """Config manager that loads YAML and provides validated settings."""
    
    def __init__(self, config_path=None, config_dict=None):
        self.raw_config = DEFAULT_CONFIG.copy()
        
        if config_path:
            p = Path(config_path)
            if not p.exists():
                raise FileNotFoundError(f"Configuration file not found: {p.resolve()}")
            with open(p, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                self.raw_config = merge_dict(self.raw_config, loaded)
        elif config_dict:
            self.raw_config = merge_dict(self.raw_config, config_dict)
            
    def get(self, key, default=None):
        """Get top-level config section or key."""
        return self.raw_config.get(key, default)
        
    @property
    def video(self):
        return self.raw_config.get("video", {})
        
    @property
    def audio(self):
        return self.raw_config.get("audio", {})
        
    @property
    def style(self):
        return self.raw_config.get("style", {})
        
    @property
    def project(self):
        return self.raw_config.get("project", {})
        
    def save(self, output_path):
        """Save current config to YAML file."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            yaml.dump(self.raw_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
