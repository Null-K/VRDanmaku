import os
import sys
import threading
import time
import asyncio
import logging
from typing import Callable, Optional

logging.getLogger('pywebview').setLevel(logging.CRITICAL)
logging.getLogger('clr_loader').setLevel(logging.CRITICAL)

if not sys.flags.debug and hasattr(sys, 'frozen'):
    sys.stderr = open(os.devnull, 'w')

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config import load_hud_config, save_hud_config, HUD_PRESETS, HMD_DEFAULT, HAND_DEFAULT
from bilibili import qr_login_async, load_credential, BiliDanmakuClient
from vr import VROverlay, VRControllerInput
from utils import set_log_callback

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


def _get_resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'ui', filename)
    return os.path.join(os.path.dirname(__file__), filename)


HTML_FILE = _get_resource_path('control_panel.html')


class AppController:
    def __init__(self):
        self.config = load_hud_config()
        self.overlay: Optional[VROverlay] = None
        self.controller: Optional[VRControllerInput] = None
        self.danmaku_client: Optional[BiliDanmakuClient] = None
        self.renderer = None
        self.window = None
        self._running = False
        self._qr_status = None
        self._qr_path = None
    
    def set_window(self, window):
        self.window = window
        set_log_callback(self.log)
    
    def log(self, msg: str, level: str = 'info'):
        if self.window:
            try:
                # 转义
                safe_msg = msg.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
                self.window.evaluate_js(f'addLog("{safe_msg}", "{level}")')
            except:
                pass
    
    def update_status(self, connected: bool, online: int = 0):
        if self.window:
            try:
                self.window.evaluate_js(f'updateConnectionStatus({str(connected).lower()}, {online})')
            except:
                pass
    
    # 配置
    def get_config(self) -> dict:
        return self.config
    
    def update_config(self, key: str, value) -> None:
        if key == 'attach_mode':
            old_mode = self.config.get('attach_mode', 'hmd')
            pos_keys = ['x', 'y', 'z', 'pitch', 'yaw', 'roll', 'scale', 'alpha', 'bg_alpha', 'font_size']
            old_config = {k: self.config[k] for k in pos_keys if k in self.config}
            self.config[old_mode] = old_config
            self.config['attach_mode'] = value
            new_config = self.config.get(value, {})
            defaults = HMD_DEFAULT if value == 'hmd' else HAND_DEFAULT
            for k in pos_keys:
                self.config[k] = new_config.get(k, defaults.get(k, 0))
        else:
            self.config[key] = value
        
        self._apply_config()
    
    def _apply_config(self):
        if self.overlay:
            self.overlay.apply_config(self.config)
        if self.renderer:
            self.renderer.set_font_size(int(self.config.get('font_size', 14)))
            self.renderer.set_show_config(self.config)
            if 'bg_alpha' in self.config:
                self.renderer.bg_alpha = self.config['bg_alpha']
        if self.controller:
            self.controller.set_toggle_hand(self.config.get('toggle_hand', 'left'))
            if self.config.get('toggle_hand') == 'always_on' and self.overlay:
                self.overlay.visible = True
    
    def apply_preset(self, name: str) -> dict:
        if name in HUD_PRESETS:
            self.config.update(HUD_PRESETS[name])
            self._apply_config()
        return self.config
    
    def reset_config(self) -> dict:
        mode = self.config.get('attach_mode', 'hmd')
        defaults = HMD_DEFAULT if mode == 'hmd' else HAND_DEFAULT
        for k, v in defaults.items():
            self.config[k] = v
        self._apply_config()
        return self.config
    
    def save_config(self) -> bool:
        save_hud_config(self.config)
        return True
    
    # VR
    def init_vr(self) -> dict:
        self._vr_init_result = None
        self._running = True
        
        threading.Thread(target=self._vr_thread, daemon=True).start()
        for _ in range(50):
            if self._vr_init_result is not None:
                break
            time.sleep(0.1)
        
        return self._vr_init_result or {"success": False, "error": "初始化超时"}
    
    def _vr_thread(self):
        try:
            from ui import DanmakuRenderer
            self.renderer = DanmakuRenderer()
            self.renderer.set_show_config(self.config)
            
            self.overlay = VROverlay()
            if not self.overlay.init():
                self._vr_init_result = {"success": False, "error": "SteamVR 未运行"}
                return
            
            self.overlay.apply_config(self.config)
            self.controller = VRControllerInput(self.overlay.vr_system)
            self.controller.on_toggle(self.overlay.toggle)
            self.controller.set_toggle_hand(self.config.get('toggle_hand', 'left'))
            
            # 检查手柄
            if not self.controller.has_controller():
                self.log("未检测到手柄, 默认使用 HUD 显示", "warning")
                self.overlay.visible = True
            elif self.config.get('toggle_hand') == 'always_on':
                self.overlay.visible = True
            
            self.log("VR 初始化完成", "success")
            
            self._vr_init_result = {"success": True}
            
            # VR 主循环
            while self._running:
                try:
                    if self.controller:
                        self.controller.poll()
                    
                    if self.overlay and self.overlay.visible and self.renderer:
                        if self.danmaku_client:
                            messages = list(self.danmaku_client.messages)
                            room_id = self.danmaku_client.room_id
                            online = self.danmaku_client.online
                            connected = self.danmaku_client.connected
                            reconnect = self.danmaku_client.reconnect_count
                        else:
                            messages = []
                            room_id = 0
                            online = 0
                            connected = False
                            reconnect = 0
                        
                        if self.renderer.should_render(len(messages)):
                            img = self.renderer.render(
                                messages, room_id, online, connected, reconnect
                            )
                            self.overlay.update_texture(img)
                except Exception as e:
                    pass
                time.sleep(0.05)
                
        except Exception as e:
            import traceback
            self._vr_init_result = {"success": False, "error": str(e)}
    
    # 弹幕
    def connect(self, room_id: int) -> dict:
        try:
            credential = load_credential()
            self.danmaku_client = BiliDanmakuClient(room_id, credential)
            
            # 保存房间号
            self.config['last_room_id'] = room_id
            save_hud_config(self.config)
            
            if not credential:
                self.log("未登录, 用户名将显示为 ***", "warning")
            
            def run():
                asyncio.run(self._connect_loop())
            
            threading.Thread(target=run, daemon=True).start()
            time.sleep(1)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _connect_loop(self):
        try:
            await self.danmaku_client.connect()
        except Exception as e:
            self.log(f"连接异常: {e}", "error")
    
    def disconnect(self) -> dict:
        if self.danmaku_client:
            self.danmaku_client.stop()
            self.danmaku_client = None
            self.log("已断开连接")
        return {"success": True}
    
    # 测试
    def send_test(self, msg_type: str) -> bool:
        if self.danmaku_client:
            self.danmaku_client.send_test_message(msg_type)
            return True
        return False
    
    # 登录凭证
    def check_credential(self) -> dict:
        cred = load_credential()
        return {"has_credential": cred is not None}
    
    def logout(self) -> bool:
        from config import CREDENTIAL_FILE
        try:
            if os.path.exists(CREDENTIAL_FILE):
                os.remove(CREDENTIAL_FILE)
            return True
        except:
            return False
    
    def start_qr_login(self) -> dict:
        self._qr_status = 'starting'
        self._qr_path = None
        self._qr_opened = False
        
        def on_status(status, qr_path):
            self._qr_status = status
            if qr_path:
                self._qr_path = qr_path
        
        def run_login():
            try:
                asyncio.run(qr_login_async(on_status))
            except Exception as e:
                self._qr_status = f'error: {e}'
        
        threading.Thread(target=run_login, daemon=True).start()
        return {"status": "started"}
    
    def get_qr_status(self) -> dict:
        # 打开二维码
        should_open = False
        if self._qr_path and not self._qr_opened and os.path.exists(self._qr_path):
            should_open = True
            self._qr_opened = True
        
        return {
            "status": self._qr_status, 
            "qr_path": self._qr_path,
            "should_open": should_open
        }
    
    def open_qr_image(self) -> dict:
        if self._qr_path and os.path.exists(self._qr_path):
            try:
                os.startfile(self._qr_path)
                return {"success": True, "path": self._qr_path}
            except Exception as e:
                return {"success": False, "error": str(e), "path": self._qr_path}
        return {"success": False, "error": "二维码文件不存在", "path": self._qr_path}
    
    def shutdown(self):
        self._running = False
        if self.danmaku_client:
            self.danmaku_client.stop()
        if self.overlay:
            self.overlay.shutdown()


class HUDControlPanel:
    def __init__(self):
        if not HAS_WEBVIEW:
            raise RuntimeError("")
        self.api = AppController()
        self.window = None
    
    def _load_html(self) -> str:
        with open(HTML_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    
    def run(self) -> None:
        def on_closed():
            self.api.shutdown()
        
        self.window = webview.create_window(
            'VRDanmaku',
            html=self._load_html(),
            width=900,
            height=700,
            resizable=True,
            js_api=self.api,
            min_size=(800, 600),
            text_select=False
        )
        self.api.set_window(self.window)
        self.window.events.closed += on_closed

        try:
            webview.start(gui='edgechromium', debug=False, private_mode=False)
        except Exception:
            try:
                webview.start(gui='cef', debug=False)
            except Exception:
                webview.start(debug=False)


def main():
    panel = HUDControlPanel()
    panel.run()


if __name__ == "__main__":
    main()
