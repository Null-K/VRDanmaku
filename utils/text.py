import datetime
from typing import List

from PIL import ImageDraw, ImageFont


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> List[str]:
    lines = []
    current_line = ""
    
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    
    if current_line:
        lines.append(current_line)
    
    return lines


def format_time(timestamp: float) -> str:
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M")
