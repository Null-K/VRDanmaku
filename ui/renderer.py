import datetime
import os
import sys
import time
from typing import List, Dict

from PIL import Image, ImageDraw, ImageFont


_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from utils.text import wrap_text, format_time


COLORS = {
    # 背景
    'bg': (18, 18, 22, 255),
    # 头部文本
    'header': (200, 200, 210),
    # 次要信息
    'header_dim': (90, 95, 105),
    # 分割线
    'separator': (45, 48, 58),
    # 时间
    'time': (60, 65, 75),
    
    # 用户名
    'user': (90, 170, 255),
    # 用户名淡
    'user_dim': (60, 110, 160),
    # 弹幕文本
    'text': (225, 228, 235),
    # 弹幕文本淡
    'text_dim': (140, 145, 155),
    # 粉丝牌
    'medal': (200, 150, 80),
    
    # 礼物
    'gift': (255, 160, 80),
    'gift_dim': (160, 110, 60),
    
    # SC 背景
    'sc_bg': (50, 45, 30),
    # SC 边框
    'sc_border': (180, 140, 50),
    # SC 文本
    'sc_text': (255, 240, 200),
    # SC 用户名
    'sc_user': (255, 200, 100),
    # SC 价格
    'sc_price': (255, 180, 60),
    
    # 进入
    'enter': (70, 160, 110),
    'enter_dim': (45, 100, 70),
    # 关注
    'follow': (240, 90, 140),
    'follow_dim': (160, 60, 100),
    # 舰长
    'guard': (255, 200, 70),
    'guard_dim': (180, 140, 50),
    
    # 在线
    'online': (70, 190, 110),
    # 连接中
    'connecting': (240, 180, 60),
    # 重连
    'reconnect': (240, 110, 80),
    
    # 警告
    'warning': (255, 80, 80),
}


class DanmakuRenderer:
    
    def __init__(self, width: int = 450, height: int = 400):
        self.width = width
        self.height = height
        self.font_size = 14
        self.bg_alpha = 0.85
        self._load_fonts(self.font_size)
        self._update_layout()
        
        # 显示开关
        self.show_config = {
            'show_danmaku': True,
            'show_gift': True,
            'show_enter': True,
            'show_follow': True,
            'show_guard': True,
            'show_sc': True,
        }
        
        # 滚动动画
        self.scroll_offset = 0.0
        self.target_scroll = 0.0
        self.last_msg_count = 0
        
        # 帧率控制
        self.last_render_time = 0
        self.idle_frame_interval = 0.2
        self.active_frame_interval = 0.05
        
        # SC 显示队列
        self.sc_display_duration = 30
    
    def _load_fonts(self, size: int) -> None:
        self.font_size = size
        try:
            self.font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size + 4)
            self.font_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
            self.font_bold = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", size)
        except Exception:
            self.font = self.font_small = self.font_bold = ImageFont.load_default()
    
    def _update_layout(self) -> None:
        fs = self.font_size
        
        # 边距
        self.padding = max(8, int(fs * 0.7))
        # 行高
        self.line_height = fs + max(6, int(fs * 0.5))
        # 项目间距
        self.item_gap = max(4, int(fs * 0.3))
        # 底部边距
        self.bottom_margin = max(4, int(fs * 0.3))
        
        # 头部布局
        self.header_padding_top = max(6, int(fs * 0.5))
        self.header_height = fs + 8 + self.header_padding_top
        self.room_line_height = fs + 4
        self.header_total = self.header_height + self.room_line_height + self.item_gap
        
        # SC 区域
        self.sc_height = self.line_height + max(6, int(fs * 0.4))
        self.sc_radius = max(4, int(fs * 0.4))
        
        # 图标宽度
        self.icon_width = fs + 4
        
        # 时间戳宽度
        self.time_width = max(35, int(fs * 2.8))
    
    def set_font_size(self, size: int) -> None:
        if size != self.font_size:
            self._load_fonts(size)
            self._update_layout()
    
    def set_show_config(self, config: dict) -> None:
        for key in self.show_config:
            if key in config:
                self.show_config[key] = config[key]
        if 'bg_alpha' in config:
            self.bg_alpha = config['bg_alpha']
    
    def _should_show(self, msg_type: str) -> bool:
        type_map = {
            'danmaku': 'show_danmaku',
            'gift': 'show_gift',
            'enter': 'show_enter',
            'follow': 'show_follow',
            'vip_enter': 'show_guard',
            'guard': 'show_guard',
            'sc': 'show_sc',
            'warning': True,
        }
        key = type_map.get(msg_type, True)
        if key is True:
            return True
        return self.show_config.get(key, True)
    
    def should_render(self, msg_count: int) -> bool:
        now = time.time()
        has_new_content = msg_count != self.last_msg_count
        is_scrolling = abs(self.target_scroll - self.scroll_offset) > 0.5
        
        interval = self.active_frame_interval if (has_new_content or is_scrolling) else self.idle_frame_interval
        
        if now - self.last_render_time >= interval:
            self.last_render_time = now
            return True
        return False
    
    def render(self, messages: List[dict], room_id: int, online: int, 
               connected: bool, reconnect_count: int) -> Image.Image:
        # 计算背景颜色
        bg_alpha_value = int(255 * self.bg_alpha)
        bg_color = COLORS['bg'][:3] + (bg_alpha_value,)
        
        img = Image.new('RGBA', (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 渲染头部
        header_bottom = self._render_header(draw, room_id, online, connected, reconnect_count)
        
        # 分离 SC 和普通消息
        now = time.time()
        sc_messages = [m for m in messages 
                       if m.get('type') == 'sc' 
                       and now - m.get('time', 0) < self.sc_display_duration
                       and self._should_show('sc')]
        normal_messages = [m for m in messages 
                          if m.get('type') != 'sc' 
                          and self._should_show(m.get('type', ''))]
        
        # SC 区域
        sc_bottom = header_bottom
        if sc_messages:
            sc_bottom = self._render_sc_area(draw, sc_messages, header_bottom)
        
        # 分隔线
        sep_y = sc_bottom + self.item_gap // 2
        draw.line([(self.padding, sep_y), (self.width - self.padding, sep_y)], fill=COLORS['separator'])
        
        # 滚动动画
        msg_count = len(normal_messages)
        if msg_count > self.last_msg_count:
            new_count = msg_count - self.last_msg_count
            self.target_scroll += new_count * self.line_height
        self.last_msg_count = msg_count
        
        if self.scroll_offset < self.target_scroll:
            self.scroll_offset += (self.target_scroll - self.scroll_offset) * 0.3
            if self.target_scroll - self.scroll_offset < 1:
                self.scroll_offset = self.target_scroll
        
        # 渲染弹幕列表
        self._render_messages(draw, normal_messages, sc_bottom + self.item_gap)
        
        return img.transpose(Image.FLIP_TOP_BOTTOM)

    def _render_header(self, draw: ImageDraw.Draw, room_id: int, online: int,
                       connected: bool, reconnect_count: int) -> int:
        now_dt = datetime.datetime.now()
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        
        y_top = self.header_padding_top
        
        # 时间
        time_str = now_dt.strftime("%H:%M")
        draw.text((self.padding, y_top), time_str, font=self.font, fill=COLORS['header'])
        
        # 日期
        date_str = f"{now_dt.month}/{now_dt.day} 周{weekdays[now_dt.weekday()]}"
        bbox = draw.textbbox((0, 0), date_str, font=self.font_small)
        date_width = bbox[2] - bbox[0]
        draw.text(((self.width - date_width) // 2, y_top + 2), date_str, font=self.font_small, fill=COLORS['header_dim'])
        
        # 状态
        if not connected:
            if reconnect_count > 0:
                status_text = f"重连({reconnect_count})"
                status_color = COLORS['reconnect']
            else:
                status_text = "连接中"
                status_color = COLORS['connecting']
        elif online:
            status_text = f"观众 {online}"
            status_color = COLORS['online']
        else:
            status_text = "●"
            status_color = COLORS['online']
        
        bbox = draw.textbbox((0, 0), status_text, font=self.font_small)
        status_width = bbox[2] - bbox[0]
        draw.text((self.width - self.padding - status_width, y_top + 2), status_text, font=self.font_small, fill=status_color)
        
        # 房间号
        room_y = y_top + self.font_size + 8
        room_text = f"#{room_id}"
        draw.text((self.padding, room_y), room_text, font=self.font_small, fill=COLORS['header_dim'])
        
        return self.header_total
    
    def _render_sc_area(self, draw: ImageDraw.Draw, sc_messages: List[dict], 
                        start_y: int) -> int:
        y = start_y
        now = time.time()
        
        for sc in sc_messages[-2:]:
            user = sc.get('user', '')[:10]
            text = sc.get('text', '')
            price = sc.get('price', 0)
            age = now - sc.get('time', now)
            
            # 计算剩余时间的透明度
            remaining = max(0, self.sc_display_duration - age)
            alpha = min(1.0, remaining / 5) if remaining < 5 else 1.0
            
            # 计算价格宽度
            price_text = f"¥{price}"
            bbox = draw.textbbox((0, 0), price_text, font=self.font_bold)
            price_width = bbox[2] - bbox[0]
            
            # 计算用户名宽度
            user_text = f"{user}: "
            bbox = draw.textbbox((0, 0), user_text, font=self.font_small)
            user_width = bbox[2] - bbox[0]
            
            # 计算文本可用宽度并换行
            content_start_x = self.padding + 6 + price_width + 6 + user_width
            text_max_width = self.width - content_start_x - self.padding - 6
            lines = wrap_text(text, self.font_small, text_max_width, draw)
            if not lines:
                lines = ['']
            
            # 计算 SC 背景高度
            sc_content_height = len(lines) * self.line_height
            sc_total_height = max(self.sc_height, sc_content_height + self.item_gap * 2)
            
            # SC 背景
            bg_alpha = int(200 * alpha)
            bg_color = COLORS['sc_bg'][:3] + (bg_alpha,)
            draw.rectangle(
                [self.padding, y, self.width - self.padding, y + sc_total_height], 
                fill=bg_color
            )
            
            # 左边框高亮
            border_color = tuple(int(c * alpha) for c in COLORS['sc_border'])
            draw.rectangle([self.padding, y, self.padding + 3, y + sc_total_height], fill=border_color)
            
            # 价格
            text_y = y + self.item_gap
            price_color = tuple(int(c * alpha) for c in COLORS['sc_price'])
            draw.text((self.padding + 8, text_y), price_text, font=self.font_bold, fill=price_color)
            
            # 用户名
            user_color = tuple(int(c * alpha) for c in COLORS['sc_user'])
            draw.text((self.padding + 8 + price_width + 6, text_y), user_text, font=self.font_small, fill=user_color)
            
            # 内容
            text_color = tuple(int(c * alpha) for c in COLORS['sc_text'])
            content_x = content_start_x + 2
            for i, line in enumerate(lines):
                if i == 0:
                    draw.text((content_x, text_y), line, font=self.font_small, fill=text_color)
                else:
                    text_y += self.line_height
                    draw.text((self.padding + 8 + price_width + 6, text_y), line, font=self.font_small, fill=text_color)
            
            y += sc_total_height + self.item_gap
        
        return y

    def _render_messages(self, draw: ImageDraw.Draw, messages: List[dict],
                         start_y: int) -> None:
        now = time.time()
        available_height = self.height - start_y - self.bottom_margin
        content_max_width = self.width - self.time_width - self.padding
        
        if not messages:
            draw.text((self.padding, start_y + self.line_height), "等待弹幕...", font=self.font_small, fill=COLORS['header_dim'])
            return

        msg_heights = []
        for msg in reversed(messages):
            height = self._calc_message_height(draw, msg, content_max_width)
            msg_heights.append((msg, height))
        
        total_height = 0
        display_msgs = []
        for msg, height in msg_heights:
            if total_height + height > available_height:
                break
            display_msgs.insert(0, (msg, height))
            total_height += height
        
        # 从上往下渲染
        y = start_y
        for msg, height in display_msgs:
            if y + height > self.height - self.bottom_margin:
                break
            
            msg_type = msg.get('type', '')
            age = now - msg.get('time', now)
            is_new = age < 3
            
            # 消息随时间变淡
            fade = max(0.4, 1.0 - (age / 60))
            
            # 新消息滑入动画
            slide_offset = 0
            if age < 0.2:
                slide_offset = int((1 - age / 0.2) * 30)
            
            y = self._render_single_message(draw, msg, msg_type, y, is_new, fade, content_max_width, slide_offset)
    
    def _calc_message_height(self, draw: ImageDraw.Draw, msg: dict, max_width: int) -> int:
        msg_type = msg.get('type', '')
        
        if msg_type != 'danmaku':
            return self.line_height
        
        # 计算弹幕前缀宽度
        prefix_width = self._calc_prefix_width(draw, msg)
        text = msg.get('text', '')
        
        # 计算文本需要的行数
        remaining_width = max_width - prefix_width
        if remaining_width < 50:
            remaining_width = max_width - self.padding
            lines = wrap_text(text, self.font_small, remaining_width, draw)
            return self.line_height * (1 + len(lines))
        
        lines = wrap_text(text, self.font_small, remaining_width, draw)
        return self.line_height * max(1, len(lines))
    
    def _calc_prefix_width(self, draw: ImageDraw.Draw, msg: dict) -> int:
        width = self.padding
        guard = msg.get('guard', 0)
        medal = msg.get('medal')
        user = msg.get('user', '')[:12]
        
        if guard:
            guard_icons = {1: '[总督]', 2: '[提督]', 3: '[舰长]'}
            icon = guard_icons.get(guard, '')
            if icon:
                bbox = draw.textbbox((0, 0), icon, font=self.font_small)
                width += bbox[2] - bbox[0] + 2
        
        if medal:
            medal_text = f"[{medal['name'][:4]}{medal['level']}]"
            bbox = draw.textbbox((0, 0), medal_text, font=self.font_small)
            width += bbox[2] - bbox[0] + 2
        
        user_text = f"{user}: "
        bbox = draw.textbbox((0, 0), user_text, font=self.font_small)
        width += bbox[2] - bbox[0]
        
        return width
    
    def _render_single_message(self, draw: ImageDraw.Draw, msg: dict, msg_type: str,
                                y: int, is_new: bool, fade: float, content_max_width: int, slide_offset: int = 0) -> int:
        user = msg.get('user', '')
        text = msg.get('text', '')
        
        x_offset = slide_offset
        
        time_str = format_time(msg.get('time', 0))
        time_color = tuple(int(c * fade) for c in COLORS['time'])
        draw.text((self.width - self.time_width + x_offset, y), time_str, font=self.font_small, fill=time_color)
        
        if msg_type == 'danmaku':
            y = self._render_danmaku(draw, msg, user[:12], text, y, is_new, fade, content_max_width, x_offset)
        elif msg_type == 'gift':
            y = self._render_gift(draw, user[:12], text, y, is_new, fade, x_offset)
        elif msg_type == 'enter':
            y = self._render_enter(draw, user[:12], y, is_new, fade, x_offset)
        elif msg_type == 'follow':
            y = self._render_follow(draw, user[:12], y, is_new, fade, x_offset)
        elif msg_type == 'vip_enter':
            y = self._render_vip_enter(draw, user, y, is_new, fade, x_offset)
        elif msg_type == 'guard':
            y = self._render_guard_buy(draw, user[:12], text, y, is_new, fade, x_offset)
        elif msg_type == 'warning':
            y = self._render_warning(draw, user, text, y, fade, x_offset)
        else:
            y += self.line_height
        
        return y
    
    def _render_danmaku(self, draw, msg, user, text, y, is_new, fade, max_width, x_offset=0) -> int:
        guard = msg.get('guard', 0)
        medal = msg.get('medal')
        
        x = self.padding + x_offset
        
        # 舰长图标
        if guard:
            guard_icons = {1: '[总督]', 2: '[提督]', 3: '[舰长]'}
            icon = guard_icons.get(guard, '')
            if icon:
                guard_color = tuple(int(c * fade) for c in COLORS['guard'])
                draw.text((x, y), icon, font=self.font_small, fill=guard_color)
                bbox = draw.textbbox((0, 0), icon, font=self.font_small)
                x += bbox[2] - bbox[0] + 2
        
        # 粉丝牌
        if medal:
            medal_text = f"[{medal['name'][:4]}{medal['level']}]"
            medal_color = tuple(int(c * fade * 0.7) for c in COLORS['medal'])
            draw.text((x, y), medal_text, font=self.font_small, fill=medal_color)
            bbox = draw.textbbox((0, 0), medal_text, font=self.font_small)
            x += bbox[2] - bbox[0] + 2
        
        # 用户名
        user_color = COLORS['user'] if is_new else COLORS['user_dim']
        user_color = tuple(int(c * fade) for c in user_color)
        user_text = f"{user}: "
        draw.text((x, y), user_text, font=self.font_small, fill=user_color)
        bbox = draw.textbbox((0, 0), user_text, font=self.font_small)
        x += bbox[2] - bbox[0]
        
        # 弹幕内容
        text_color = COLORS['text'] if is_new else COLORS['text_dim']
        text_color = tuple(int(c * fade) for c in text_color)
        
        remaining_width = max_width - x + self.padding

        if remaining_width < 50:
            y += self.line_height
            x = self.padding
            remaining_width = max_width - self.padding
        
        lines = wrap_text(text, self.font_small, remaining_width, draw)
        
        if lines:
            draw.text((x, y), lines[0], font=self.font_small, fill=text_color)
            y += self.line_height
            for line in lines[1:]:
                draw.text((self.padding, y), line, font=self.font_small, fill=text_color)
                y += self.line_height
        else:
            y += self.line_height
        
        return y

    def _render_gift(self, draw, user, text, y, is_new, fade, x_offset=0) -> int:
        color = COLORS['gift'] if is_new else COLORS['gift_dim']
        color = tuple(int(c * fade) for c in color)
        draw.text((self.padding + x_offset, y), f"[礼物] {user} {text}", font=self.font_small, fill=color)
        return y + self.line_height
    
    def _render_enter(self, draw, user, y, is_new, fade, x_offset=0) -> int:
        color = COLORS['enter'] if is_new else COLORS['enter_dim']
        color = tuple(int(c * fade) for c in color)
        draw.text((self.padding + x_offset, y), f"[加入] {user} 进入", font=self.font_small, fill=color)
        return y + self.line_height
    
    def _render_follow(self, draw, user, y, is_new, fade, x_offset=0) -> int:
        color = COLORS['follow'] if is_new else COLORS['follow_dim']
        color = tuple(int(c * fade) for c in color)
        draw.text((self.padding + x_offset, y), f"[关注] {user} 关注了直播间", font=self.font_small, fill=color)
        return y + self.line_height
    
    def _render_vip_enter(self, draw, user, y, is_new, fade, x_offset=0) -> int:
        color = COLORS['guard'] if is_new else COLORS['guard_dim']
        color = tuple(int(c * fade) for c in color)
        draw.text((self.padding + x_offset, y), f"[舰长] {user}", font=self.font_small, fill=color)
        return y + self.line_height
    
    def _render_guard_buy(self, draw, user, text, y, is_new, fade, x_offset=0) -> int:
        color = COLORS['guard'] if is_new else COLORS['guard_dim']
        color = tuple(int(c * fade) for c in color)
        draw.text((self.padding + x_offset, y), f"[上舰] {user} {text}", font=self.font_small, fill=color)
        return y + self.line_height
    
    def _render_warning(self, draw, user, text, y, fade, x_offset=0) -> int:
        color = tuple(int(c * fade) for c in COLORS['warning'])
        draw.text((self.padding + x_offset, y), f"{user} {text}", font=self.font_small, fill=color)
        return y + self.line_height
