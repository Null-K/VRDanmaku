import datetime
from typing import List, Dict

from PIL import ImageDraw, ImageFont


# 字符宽度缓存，避免重复测量
_char_width_cache: Dict[int, Dict[str, int]] = {}


def _get_char_width(char: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw) -> int:
    font_id = id(font)
    cache = _char_width_cache.get(font_id)
    if cache is None:
        cache = {}
        _char_width_cache[font_id] = cache
    
    w = cache.get(char)
    if w is None:
        bbox = draw.textbbox((0, 0), char, font=font)
        w = bbox[2] - bbox[0]
        cache[char] = w
    return w


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    if not text:
        return []
    
    lines = []
    current_line = ""
    current_width = 0
    
    for char in text:
        char_w = _get_char_width(char, font, draw)
        
        if current_width + char_w <= max_width:
            current_line += char
            current_width += char_w
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
            current_width = char_w
    
    if current_line:
        lines.append(current_line)
    
    return lines


def format_time(timestamp: float) -> str:
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M")
