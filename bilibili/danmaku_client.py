import asyncio
import time
from collections import deque
from typing import Optional, Callable

from bilibili_api import live, Credential
from utils import log


class BiliDanmakuClient:
    
    def __init__(self, room_id: int, credential: Optional[Credential] = None):
        self.room_id = room_id
        self.credential = credential
        self.messages = deque(maxlen=50)
        self.online = 0
        self.running = False
        self.connected = False
        self.reconnect_count = 0
        
        self.room = live.LiveDanmaku(room_id, credential=credential)
        self._register_events()
    
    def _register_events(self) -> None:
        
        @self.room.on('DANMU_MSG')
        async def on_danmaku(event):
            info = event['data']['info']
            user = info[2][1] if len(info) > 2 and len(info[2]) > 1 else '???'
            text = info[1] if len(info) > 1 else ''
            
            medal = None
            if len(info) > 3 and info[3]:
                medal_info = info[3]
                if len(medal_info) >= 2:
                    medal = {'name': medal_info[1], 'level': medal_info[0]}
            
            guard_level = info[7] if len(info) > 7 else 0
            
            self.messages.append({
                'type': 'danmaku', 'user': user, 'text': text,
                'medal': medal, 'guard': guard_level, 'time': time.time()
            })
            log(f"[弹幕] {user}: {text}")
        
        @self.room.on('SEND_GIFT')
        async def on_gift(event):
            data = event['data'].get('data', {})
            user = data.get('uname', '???')
            gift = data.get('giftName', '礼物')
            num = data.get('num', 1)
            
            # 礼物连击合并
            now = time.time()
            for msg in reversed(list(self.messages)):
                if (msg.get('type') == 'gift' and 
                    msg.get('user') == user and 
                    msg.get('gift_name') == gift and
                    now - msg.get('time', 0) < 5):

                    msg['gift_count'] = msg.get('gift_count', 0) + num
                    msg['text'] = f"{gift} x{msg['gift_count']}"
                    msg['time'] = now
                    log(f"[礼物] {user}: {gift} x{msg['gift_count']}")
                    return
            
            # 新礼物
            self.messages.append({
                'type': 'gift', 'user': user, 'text': f'{gift} x{num}',
                'gift_name': gift, 'gift_count': num,
                'time': now
            })
            log(f"[礼物] {user}: {gift} x{num}")
        
        @self.room.on('SUPER_CHAT_MESSAGE')
        async def on_sc(event):
            self._handle_sc(event)
        
        @self.room.on('SUPER_CHAT_MESSAGE_NEW')
        async def on_sc_new(event):
            self._handle_sc(event)

        @self.room.on('INTERACT_WORD')
        async def on_enter(event):
            self._handle_interact(event)
        
        @self.room.on('INTERACT_WORD_V2')
        async def on_enter_v2(event):
            self._handle_interact(event)
        
        @self.room.on('ENTRY_EFFECT')
        async def on_entry_effect(event):
            data = event['data'].get('data', {})
            user = data.get('copy_writing', '').replace('<%', '').replace('%>', '')
            if user:
                self.messages.append({
                    'type': 'vip_enter', 'user': user, 'text': '',
                    'time': time.time()
                })
                log(f"[舰长] {user}")
        
        @self.room.on('WARNING')
        async def on_warning(event):
            data = event['data'].get('data', event['data'])
            msg = data.get('msg', '直播间收到警告')
            self.messages.append({
                'type': 'warning', 'user': '[警告] ', 'text': msg,
                'time': time.time()
            })
            log(f"[警告] {msg}", 'warning')
        
        @self.room.on('CUT_OFF')
        async def on_cut_off(event):
            data = event['data'].get('data', event['data'])
            msg = data.get('msg', '直播被切断')
            self.messages.append({
                'type': 'warning', 'user': '[切断] ', 'text': msg,
                'time': time.time()
            })
            log(f"[切断] {msg}", 'error')
        
        @self.room.on('GUARD_BUY')
        async def on_guard_buy(event):
            data = event['data'].get('data', {})
            user = data.get('username', '???')
            guard_level = data.get('guard_level', 0)
            gift_name = data.get('gift_name', '舰长')
            guard_names = {1: '总督', 2: '提督', 3: '舰长'}
            guard_name = guard_names.get(guard_level, gift_name)
            self.messages.append({
                'type': 'guard', 'user': user, 'text': f'开通了{guard_name}',
                'guard_level': guard_level,
                'time': time.time()
            })
            log(f"[上舰] {user} 开通了{guard_name}")
        
        @self.room.on('ROOM_LOCK')
        async def on_room_lock(event):
            self.messages.append({
                'type': 'warning', 'user': '[封禁] ', 'text': '直播间已被封禁',
                'time': time.time()
            })
            log("[封禁] 直播间已被封禁", 'error')
        
        @self.room.on('ONLINE_RANK_COUNT')
        async def on_online(event):
            data = event['data'].get('data', {})
            count = data.get('count', 0)
            if count > 0:
                self.online = count
    
    def _handle_sc(self, event) -> None:
        data = event['data'].get('data', {})
        user = data.get('user_info', {}).get('uname', '???')
        text = data.get('message', '')
        price = data.get('price', 0)
        
        # 去重：避免同一条 SC 被两个事件重复添加
        now = time.time()
        for msg in reversed(list(self.messages)):
            if (msg.get('type') == 'sc' and
                msg.get('user') == user and
                msg.get('text') == text and
                msg.get('price') == price and
                now - msg.get('time', 0) < 5):
                return
        
        self.messages.append({
            'type': 'sc', 'user': user, 'text': text, 'price': price,
            'time': now
        })
        log(f"[SC {price}元] {user}: {text}")
    
    def _handle_interact(self, event) -> None:
        data = event['data'].get('data', {})
        
        # 兼容多种数据结构
        # V1: 直接在 data 中有 uname / msg_type
        # V2: 可能在 pb_decoded 中，也可能直接在 data 中
        user = ''
        msg_type = 1
        
        pb = data.get('pb_decoded', {})
        if pb:
            user = pb.get('uname', '')
            if not user:
                user = pb.get('user_info', {}).get('base', {}).get('name', '')
            msg_type = pb.get('msg_type', 1)
        
        if not user:
            user = data.get('uname', '')
        if not user:
            user = data.get('user_info', {}).get('base', {}).get('name', '')
        if not user:
            return
        
        if 'msg_type' in data:
            msg_type = data.get('msg_type', 1)
        
        now = time.time()
        # 去重：短时间内同一用户的重复进入事件
        for msg in reversed(list(self.messages)):
            if (msg.get('type') == 'enter' and
                msg.get('user') == user and
                now - msg.get('time', 0) < 3):
                return
        
        if msg_type == 1:
            self.messages.append({
                'type': 'enter', 'user': user, 'text': '进入直播间',
                'time': now
            })
            log(f"[进入] {user}")
        elif msg_type == 2:
            self.messages.append({
                'type': 'follow', 'user': user, 'text': '关注了直播间',
                'time': now
            })
            log(f"[关注] {user}")
    
    async def connect(self) -> None:
        self.running = True
        while self.running:
            try:
                self.connected = True
                self.reconnect_count = 0
                log(f"正在连接房间 {self.room_id}")
                await self.room.connect()
            except Exception as e:
                self.connected = False
                error_msg = str(e)
                if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                    log("连接超时", 'error')
                elif 'connection' in error_msg.lower():
                    log("网络连接失败", 'error')
                else:
                    log(f"连接错误: {error_msg}", 'error')
            if self.running:
                self.reconnect_count += 1
                # 指数退避：3s, 6s, 12s, 24s... 最大 60s
                delay = min(60, 3 * (2 ** (self.reconnect_count - 1)))
                log(f"{delay}秒后重连 (第{self.reconnect_count}次)", 'warning')
                await asyncio.sleep(delay)
    
    def stop(self) -> None:
        self.running = False
        self.connected = False
        # 通知正在运行的事件循环去断开连接，而不是创建新循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(self._schedule_disconnect, loop)
            else:
                # 没有运行中的循环，直接用新循环断开
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.room.disconnect())
                loop.close()
        except Exception:
            pass
    
    def _schedule_disconnect(self, loop) -> None:
        asyncio.ensure_future(self._safe_disconnect(), loop=loop)
    
    async def _safe_disconnect(self) -> None:
        try:
            await self.room.disconnect()
        except Exception:
            pass
    
    # 测试方法
    def send_test_message(self, msg_type: str = 'sc') -> None:
        if msg_type == 'sc':
            self.messages.append({
                'type': 'sc',
                'user': '测试用户',
                'text': '这是一条测试SC消息，用于测试显示效果，这是第二行，用于测试换行效果。',
                'price': 30,
                'time': time.time()
            })
        elif msg_type == 'danmaku':
            self.messages.append({
                'type': 'danmaku',
                'user': '测试用户',
                'text': '这是一条测试弹幕',
                'medal': {'name': '测试', 'level': 20},
                'guard': 3,
                'time': time.time()
            })
        elif msg_type == 'gift':
            self.messages.append({
                'type': 'gift',
                'user': '测试用户',
                'text': '小电视飞船 x1',
                'time': time.time()
            })
        elif msg_type == 'warning':
            self.messages.append({
                'type': 'warning',
                'user': '[警告]',
                'text': '直播内容涉及敏感话题，请注意规范',
                'time': time.time()
            })
        elif msg_type == 'enter':
            self.messages.append({
                'type': 'enter',
                'user': '测试用户',
                'text': '进入直播间',
                'time': time.time()
            })
