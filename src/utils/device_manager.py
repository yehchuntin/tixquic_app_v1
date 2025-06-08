"""
設備管理器
生成和管理設備指紋
"""

import platform
import hashlib
import uuid
import json
import os
import datetime  # ← 加入這行
from typing import Dict, Any

class DeviceManager:
    def __init__(self):
        self.device_file = "device_id.json"
        self.device_info = self._load_or_create_device_info()
        
    def get_device_id(self) -> str:
        """獲取設備 ID"""
        return self.device_info['device_id']
        
    def get_device_fingerprint(self) -> str:
        """獲取設備指紋"""
        return self.device_info['fingerprint']
        
    def _load_or_create_device_info(self) -> Dict[str, Any]:
        """載入或建立設備資訊"""
        if os.path.exists(self.device_file):
            try:
                with open(self.device_file, 'r') as f:
                    return json.load(f)
            except:
                pass
                
        # 建立新的設備資訊
        device_info = self._create_device_info()
        self._save_device_info(device_info)
        return device_info
        
    def _create_device_info(self) -> Dict[str, Any]:
        """建立設備資訊"""
        # 收集系統資訊
        system_info = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release()
        }
        
        # 生成唯一 ID
        device_id = str(uuid.uuid4())
        
        # 生成指紋
        fingerprint_data = json.dumps(system_info, sort_keys=True) + device_id
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        
        return {
            "device_id": device_id,
            "fingerprint": fingerprint,
            "system_info": system_info,
            "created_at": str(datetime.datetime.now())
        }
        
    def _save_device_info(self, device_info: Dict[str, Any]):
        """儲存設備資訊"""
        try:
            with open(self.device_file, 'w') as f:
                json.dump(device_info, f, indent=2)
        except:
            pass
            
    def get_system_info(self) -> Dict[str, Any]:
        """獲取系統資訊"""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "python_version": platform.python_version()
        }

import datetime  # 加在檔案開頭