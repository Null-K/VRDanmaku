import json
import os
import sys
import asyncio
import tempfile

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config import CREDENTIAL_FILE
from bilibili_api import Credential
from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents


def load_credential():
    if not os.path.exists(CREDENTIAL_FILE):
        return None
    
    try:
        with open(CREDENTIAL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sessdata = data.get('sessdata', '').strip()
            bili_jct = data.get('bili_jct', '').strip()
            
            if sessdata and bili_jct:
                return Credential(
                    sessdata=sessdata,
                    bili_jct=bili_jct,
                    buvid3=data.get('buvid3', '').strip()
                )
    except Exception:
        pass
    
    return None


def save_credential(credential: Credential) -> None:
    data = {
        "sessdata": credential.sessdata or "",
        "bili_jct": credential.bili_jct or "",
        "buvid3": credential.buvid3 or "",
    }
    with open(CREDENTIAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def create_credential_template() -> None:
    if os.path.exists(CREDENTIAL_FILE):
        return
    
    template = {
        "sessdata": "",
        "bili_jct": "",
        "buvid3": "",
    }
    with open(CREDENTIAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)


async def qr_login_async(on_status=None):
    try:
        qr = QrCodeLogin()
        await qr.generate_qrcode()
        
        # 保存二维码
        qr_pic = qr.get_qrcode_picture()
        qr_path = os.path.join(tempfile.gettempdir(), 'bili_qr.png')
        
        # 获取图片
        if qr_pic.content:
            with open(qr_path, 'wb') as f:
                f.write(qr_pic.content)
        else:
            qr_pic.to_file(qr_path)
        
        if on_status:
            on_status('waiting', qr_path)
        
        # 检查状态
        while True:
            state = await qr.check_state()
            
            if state == QrCodeLoginEvents.SCAN:
                if on_status:
                    on_status('scanned', qr_path)
            elif state == QrCodeLoginEvents.CONF:
                if on_status:
                    on_status('confirming', qr_path)
            elif state == QrCodeLoginEvents.TIMEOUT:
                if on_status:
                    on_status('timeout', None)
                return None
            elif state == QrCodeLoginEvents.DONE:
                credential = qr.get_credential()
                save_credential(credential)
                if on_status:
                    on_status('done', None)
                return credential
            
            await asyncio.sleep(1)
    except Exception as e:
        if on_status:
            on_status(f'error: {e}', None)
        return None
