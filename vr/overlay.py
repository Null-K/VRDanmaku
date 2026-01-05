import ctypes
import math
from typing import Optional

import openvr
from OpenGL import GL
import glfw
from PIL import Image


class VROverlay:
    
    def __init__(self, width: int = 450, height: int = 400):
        self.width = width
        self.height = height
        self.vr_system: Optional[openvr.IVRSystem] = None
        self.overlay: Optional[openvr.IVROverlay] = None
        self.overlay_handle: Optional[int] = None
        self.texture_id: Optional[int] = None
        self.visible = True
        self.config = {}
    
    def init(self) -> bool:
        # OpenGL 初始化
        if not glfw.init():
            return False
        
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        window = glfw.create_window(self.width, self.height, "", None, None)
        if not window:
            return False
        
        glfw.make_context_current(window)
        self.texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        
        # OpenVR 初始化
        try:
            self.vr_system = openvr.init(openvr.VRApplication_Overlay)
            self.overlay = openvr.IVROverlay()
            self.overlay_handle = self.overlay.createOverlay(
                "vr_bili_danmaku", "VR Bilibili Danmaku"
            )
            self.overlay.showOverlay(self.overlay_handle)
            return True
        except Exception:
            return False
    
    def apply_config(self, config: dict) -> None:
        self.config = config
        self.overlay.setOverlayWidthInMeters(
            self.overlay_handle, config.get('scale', 0.4)
        )
        self.overlay.setOverlayAlpha(
            self.overlay_handle, config.get('alpha', 0.92)
        )
        
        attach_mode = config.get('attach_mode', 'hmd')
        x = config.get('x', -0.4)
        y = config.get('y', 0.1)
        z = config.get('z', -0.8)
        pitch = math.radians(config.get('pitch', 0))
        yaw = math.radians(config.get('yaw', 0))
        roll = math.radians(config.get('roll', 0))
        
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cr, sr = math.cos(roll), math.sin(roll)
        
        transform = openvr.HmdMatrix34_t()
        
        if attach_mode == 'hand':
            transform[0] = (1.0, 0.0, 0.0, x)
            transform[1] = (0.0, 0.0, 1.0, y)
            transform[2] = (0.0, -1.0, 0.0, z)
            
            left_hand = self._find_left_controller()
            if left_hand != openvr.k_unTrackedDeviceIndexInvalid:
                self.overlay.setOverlayTransformTrackedDeviceRelative(
                    self.overlay_handle, left_hand, transform
                )
            else:
                self._apply_hmd_transform(transform, x, y, z, cp, sp, cy, sy, cr, sr)
        else:
            self._apply_hmd_transform(transform, x, y, z, cp, sp, cy, sy, cr, sr)
    
    def _find_left_controller(self) -> int:
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_Controller:
                role = self.vr_system.getControllerRoleForTrackedDeviceIndex(i)
                if role == openvr.TrackedControllerRole_LeftHand:
                    return i
        return openvr.k_unTrackedDeviceIndexInvalid
    
    def _apply_hmd_transform(self, transform, x, y, z, cp, sp, cy, sy, cr, sr) -> None:
        transform[0] = (cy * cr, -cy * sr, sy, x)
        transform[1] = (sp * sy * cr + cp * sr, -sp * sy * sr + cp * cr, -sp * cy, y)
        transform[2] = (-cp * sy * cr + sp * sr, cp * sy * sr + sp * cr, cp * cy, z)
        self.overlay.setOverlayTransformTrackedDeviceRelative(
            self.overlay_handle, openvr.k_unTrackedDeviceIndex_Hmd, transform
        )
    
    def update_texture(self, img: Image.Image) -> None:
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture_id)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA,
            self.width, self.height, 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, img.tobytes()
        )
        
        texture = openvr.Texture_t()
        texture.handle = ctypes.c_void_p(int(self.texture_id))
        texture.eType = openvr.TextureType_OpenGL
        texture.eColorSpace = openvr.ColorSpace_Gamma
        self.overlay.setOverlayTexture(self.overlay_handle, texture)
    
    def show(self) -> None:
        self.visible = True
        self.overlay.showOverlay(self.overlay_handle)
    
    def hide(self) -> None:
        self.visible = False
        self.overlay.hideOverlay(self.overlay_handle)
    
    # 开关隐藏
    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()
    
    def shutdown(self) -> None:
        if self.overlay and self.overlay_handle:
            try:
                self.overlay.destroyOverlay(self.overlay_handle)
            except Exception:
                pass
        if self.vr_system:
            try:
                openvr.shutdown()
            except Exception:
                pass
        glfw.terminate()
