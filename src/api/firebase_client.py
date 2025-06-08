# -*- coding: utf-8 -*-
"""
修正後的 Firebase API 客戶端
處理與 Firebase Functions 的通訊，支援設備綁定防共用
"""

import requests
import base64
import hashlib
import platform
import uuid
import subprocess
from typing import Dict, Any, Optional
import json

class FirebaseClient:
    def __init__(self):
        # 修正後的 Firebase Functions v2 URL
        self.base_url = "https://us-central1-ticketswift-al241.cloudfunctions.net"
        self.device_fingerprint = self._generate_device_fingerprint()
        
    def _generate_device_fingerprint(self) -> str:
        """生成設備指紋"""
        try:
            if platform.system() == "Windows":
                # Windows: 使用主板序號 + CPU ID
                try:
                    cmd = ['wmic', 'baseboard', 'get', 'serialnumber']
                    result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
                    board_serial = result.split('\n')[1].strip()
                    
                    cmd = ['wmic', 'cpu', 'get', 'processorid']
                    result = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
                    cpu_id = result.split('\n')[1].strip()
                    
                    device_info = f"{board_serial}-{cpu_id}"
                except:
                    # 備用方案
                    device_info = f"{platform.node()}-{uuid.uuid4().hex}"
                    
            elif platform.system() == "Darwin":  # macOS
                try:
                    # macOS: 使用硬體 UUID
                    cmd = ['system_profiler', 'SPHardwareDataType']
                    result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
                    
                    hardware_uuid = "unknown"
                    for line in result.split('\n'):
                        if 'Hardware UUID' in line:
                            hardware_uuid = line.split(':')[1].strip()
                            break
                    
                    device_info = f"{hardware_uuid}-{platform.machine()}"
                except:
                    device_info = f"{platform.node()}-{uuid.uuid4().hex}"
            
            else:
                # Linux 或其他系統
                device_info = f"{platform.node()}-{platform.machine()}-{uuid.uuid1().hex}"
            
            # 生成最終指紋
            fingerprint = hashlib.sha256(device_info.encode()).hexdigest()[:32]
            print(f"🔧 設備指紋: {fingerprint}")
            return fingerprint
            
        except Exception as e:
            print(f"⚠️ 生成設備指紋失敗，使用備用方案: {e}")
            fallback = f"{platform.system()}-{platform.machine()}-{uuid.uuid4().hex}"
            return hashlib.sha256(fallback.encode()).hexdigest()[:32]
    
    def verify_and_fetch_config(self, verification_code: str, force_unbind: bool = False) -> Dict[str, Any]:
        """
        驗證驗證碼並獲取配置
        包含活動資訊、使用者偏好設定、OpenAI API Key
        """
        # 修正後的 URL
        url = f"{self.base_url}/verifyAndFetchConfig"
        
        payload = {
            "verificationCode": verification_code,
            "deviceFingerprint": self.device_fingerprint,
            "forceUnbind": force_unbind
        }
        
        try:
            print(f"🔄 正在驗證驗證碼: {verification_code}")
            print(f"🔗 請求 URL: {url}")
            
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"TicketGrabber/{platform.system()}"
                },
                timeout=30
            )
            
            print(f"📡 回應狀態: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    if result.get('success'):
                        # 解密 API Key
                        if 'apiKey' in result.get('data', {}):
                            result['data']['apiKey'] = self._decrypt_api_key(
                                result['data']['apiKey']
                            )
                        
                        # 顯示設備綁定狀態
                        device_info = result.get('data', {}).get('bindingInfo', {})
                        print(f"✅ 設備綁定狀態: {device_info.get('policy', 'strict')}")
                        
                        return result
                    else:
                        return result
                        
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "message": f"伺服器回應格式錯誤: {str(e)}"
                    }
            
            elif response.status_code == 403:
                try:
                    error_response = response.json()
                    # 檢查是否可以強制解綁
                    binding_info = error_response.get('bindingInfo', {})
                    if binding_info.get('canForceUnbind'):
                        # 詢問用戶是否要強制解綁
                        return {
                            "success": False,
                            "message": error_response.get('message'),
                            "can_force_unbind": True,
                            "binding_info": binding_info
                        }
                    else:
                        return error_response
                except:
                    return {
                        "success": False,
                        "message": "此驗證碼已在其他設備上使用，無法在本設備使用"
                    }
            
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": "驗證碼不存在或已過期"
                }
            
            else:
                try:
                    error_response = response.json()
                    return error_response
                except:
                    return {
                        "success": False,
                        "message": f"伺服器錯誤 ({response.status_code})"
                    }
                    
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "message": "無法連接到伺服器，請檢查網路連線"
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "請求超時，請稍後再試"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"未預期的錯誤: {str(e)}"
            }
    
    def mark_code_as_used(self, verification_code: str, 
                         status: str = "completed", 
                         details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        標記驗證碼為已使用
        """
        url = f"{self.base_url}/markCodeAsUsed"
        
        payload = {
            "verificationCode": verification_code,
            "deviceFingerprint": self.device_fingerprint,
            "status": status,
            "details": details or {}
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ 使用狀態已更新: {result.get('message')}")
                return result
            else:
                return response.json()
                
        except Exception as e:
            print(f"⚠️ 無法更新使用狀態: {str(e)}")
            return {
                "success": False,
                "message": f"狀態更新失敗: {str(e)}"
            }
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """
        解密 API Key
        """
        try:
            # 先檢查是否已經是明文
            if encrypted_key.startswith('sk-'):
                return encrypted_key
                
            # 嘗試 base64 解碼
            decoded = base64.b64decode(encrypted_key).decode('utf-8')
            return decoded
        except Exception as e:
            print(f"⚠️ API Key 解密失敗: {str(e)}")
            return encrypted_key
    
    def get_device_info(self) -> Dict[str, str]:
        """獲取設備資訊"""
        return {
            "device_fingerprint": self.device_fingerprint,
            "platform": platform.system(),
            "architecture": platform.architecture()[0],
            "machine": platform.machine(),
            "node": platform.node()
        }