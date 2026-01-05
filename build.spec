# pyinstaller build.spec

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

CURRENT_DIR = os.path.dirname(os.path.abspath(SPEC))

import openvr
openvr_dir = os.path.dirname(openvr.__file__)

import glfw
glfw_dir = os.path.dirname(glfw.__file__)

bilibili_datas, bilibili_binaries, bilibili_hiddenimports = collect_all('bilibili_api')
aiohttp_datas, aiohttp_binaries, aiohttp_hiddenimports = collect_all('aiohttp')

binaries_list = bilibili_binaries + aiohttp_binaries

openvr_dll = os.path.join(openvr_dir, 'libopenvr_api_64.dll')
if os.path.exists(openvr_dll):
    binaries_list.append((openvr_dll, 'openvr'))

glfw_dll = os.path.join(glfw_dir, 'glfw3.dll')
if os.path.exists(glfw_dll):
    binaries_list.append((glfw_dll, 'glfw'))

a = Analysis(
    ['main.py'],
    pathex=[CURRENT_DIR],
    binaries=binaries_list,
    datas=[
        ('ui/control_panel.html', 'ui'),
    ] + bilibili_datas + aiohttp_datas,
    hiddenimports=[
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'clr_loader',
        'pythonnet',
        # PIL
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # OpenGL
        'OpenGL',
        'OpenGL.GL',
        'OpenGL.platform',
        'OpenGL.platform.win32',
        # 网络
        'yarl',
        'multidict',
        'async_timeout',
        'brotli',
        'certifi',
        'charset_normalizer',
        'httpx',
        'httpcore',
        'anyio',
        'sniffio',
        'h11',
        # protobuf
        'google.protobuf',
        'google.protobuf.internal',
        # 其他
        'glfw',
        'openvr',
        'ctypes',
        'json',
        'asyncio',
        'threading',
    ] + bilibili_hiddenimports + aiohttp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VRDanmaku',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python*.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
