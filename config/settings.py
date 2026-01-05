import json
import os


CREDENTIAL_FILE = "bili_credential.json"
HUD_CONFIG_FILE = "vr_hud_position.json"

# 头显默认配置
HMD_DEFAULT = {
    "x": -0.4, "y": 0.1, "z": -0.8,
    "pitch": 0, "yaw": 15, "roll": 0,
    "scale": 0.4, "alpha": 0.92,
    "bg_alpha": 0.85,
    "font_size": 14
}

# 左手默认配置
HAND_DEFAULT = {
    "x": 0, "y": 0.08, "z": -0.1,
    "pitch": -30, "yaw": 0, "roll": 0,
    "scale": 0.25, "alpha": 0.95,
    "bg_alpha": 0.9,
    "font_size": 12
}

# 开关默认配置
DISPLAY_DEFAULT = {
    "show_danmaku": True,
    "show_gift": True,
    "show_enter": True,
    "show_follow": True,
    "show_guard": True,
    "show_sc": True,
    "toggle_hand": "left",
    "last_room_id": 0,
}

DEFAULT_HUD_CONFIG = {
    "attach_mode": "hmd",
    "hmd": HMD_DEFAULT.copy(),
    "hand": HAND_DEFAULT.copy(),
    **DISPLAY_DEFAULT
}

HUD_PRESETS = {
    "left": {"x": -0.4, "y": 0.1, "z": -0.8, "pitch": 0, "yaw": 15, "roll": 0},
    "center": {"x": 0, "y": 0, "z": -0.8, "pitch": 0, "yaw": 0, "roll": 0},
    "right": {"x": 0.4, "y": 0.1, "z": -0.8, "pitch": 0, "yaw": -15, "roll": 0},
    "top_left": {"x": -0.3, "y": 0.3, "z": -0.7, "pitch": -15, "yaw": 10, "roll": 0},
    "top": {"x": 0, "y": 0.4, "z": -0.6, "pitch": -25, "yaw": 0, "roll": 0},
}


def load_hud_config() -> dict:
    config = DEFAULT_HUD_CONFIG.copy()
    config['hmd'] = HMD_DEFAULT.copy()
    config['hand'] = HAND_DEFAULT.copy()
    
    if os.path.exists(HUD_CONFIG_FILE):
        try:
            with open(HUD_CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config['attach_mode'] = saved.get('attach_mode', 'hmd')
                if 'hmd' in saved:
                    config['hmd'].update(saved['hmd'])
                if 'hand' in saved:
                    config['hand'].update(saved['hand'])
                for key in DISPLAY_DEFAULT:
                    if key in saved:
                        config[key] = saved[key]
        except Exception:
            pass

    return get_flat_config(config)


def get_flat_config(config: dict) -> dict:
    mode = config.get('attach_mode', 'hmd')
    mode_config = config.get(mode, {})
    flat = {
        'attach_mode': mode,
        'hmd': config.get('hmd', HMD_DEFAULT.copy()),
        'hand': config.get('hand', HAND_DEFAULT.copy()),
        **mode_config
    }
    # 显示开关
    for key in DISPLAY_DEFAULT:
        if key in config:
            flat[key] = config[key]
        elif key not in flat:
            flat[key] = DISPLAY_DEFAULT[key]
    return flat


def save_hud_config(config: dict) -> None:
    mode = config.get('attach_mode', 'hmd')
    
    pos_keys = ['x', 'y', 'z', 'pitch', 'yaw', 'roll', 'scale', 'alpha', 'bg_alpha', 'font_size']
    mode_config = {k: config[k] for k in pos_keys if k in config}

    save_data = {
        'attach_mode': mode,
        'hmd': config.get('hmd', HMD_DEFAULT.copy()),
        'hand': config.get('hand', HAND_DEFAULT.copy())
    }
    save_data[mode] = mode_config
    
    for key in DISPLAY_DEFAULT:
        if key in config:
            save_data[key] = config[key]
    
    with open(HUD_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
