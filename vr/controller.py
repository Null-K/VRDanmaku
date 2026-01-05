import time
from typing import Callable, Optional

import openvr


class VRControllerInput:
    
    def __init__(self, vr_system: openvr.IVRSystem):
        self.vr_system = vr_system
        self.grip_was_pressed = False
        self.last_toggle_time = 0
        self.toggle_cooldown = 0.5
        self._on_toggle_callback: Optional[Callable] = None
        # left, right, always_on
        self.toggle_hand = "left"  
        self._controller_found = False
    
    def on_toggle(self, callback: Callable) -> None:
        self._on_toggle_callback = callback
    
    def set_toggle_hand(self, hand: str) -> None:
        self.toggle_hand = hand
    
    def _find_controller(self, role: int) -> int:
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) != openvr.TrackedDeviceClass_Controller:
                continue
            if self.vr_system.getControllerRoleForTrackedDeviceIndex(i) == role:
                return i
        return openvr.k_unTrackedDeviceIndexInvalid
    
    def has_controller(self) -> bool:
        left = self._find_controller(openvr.TrackedControllerRole_LeftHand)
        right = self._find_controller(openvr.TrackedControllerRole_RightHand)
        return left != openvr.k_unTrackedDeviceIndexInvalid or right != openvr.k_unTrackedDeviceIndexInvalid
    
    def poll(self) -> None:
        # 常开模式
        if self.toggle_hand == "always_on":
            return
        
        now = time.time()
        target_role = (openvr.TrackedControllerRole_LeftHand 
                       if self.toggle_hand == "left" 
                       else openvr.TrackedControllerRole_RightHand)
        
        controller_idx = self._find_controller(target_role)
        
        # 未找到手柄
        if controller_idx == openvr.k_unTrackedDeviceIndexInvalid:
            if self._controller_found:
                self._controller_found = False
            return
        
        if not self._controller_found:
            self._controller_found = True
        
        result, state = self.vr_system.getControllerState(controller_idx)
        if not result:
            return
        
        grip_pressed = bool(state.ulButtonPressed & (1 << openvr.k_EButton_Grip))
        
        if grip_pressed and not self.grip_was_pressed:
            if now - self.last_toggle_time > self.toggle_cooldown:
                self.last_toggle_time = now
                if self._on_toggle_callback:
                    self._on_toggle_callback()
        
        self.grip_was_pressed = grip_pressed
