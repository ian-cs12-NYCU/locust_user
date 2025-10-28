import json
import os
import itertools
from threading import Lock
from pathlib import Path

class SourceIpManager:
    """
    一個 IP 管理器，為不同類型的 User 創建和管理獨立的 IP 分配器。
    它從設定檔 (profiles/ips.json) 讀取 IP 列表，並為每個 User 類型提供一個
    獨立的、可循環的 IP 分配器。
    """
    _instance = None
    _manager_lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._manager_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        with self._manager_lock:
            if hasattr(self, '_initialized'):
                return

            print(f"[IpManager] Initializing...")
            base_dir = Path(__file__).parent.parent
            self.config_file = base_dir / 'profiles' / 'ips.json'
            self.ips = self._load_ips()
            
            if not self.ips:
                raise ValueError(f"IP list in '{self.config_file}' is empty or not found.")
            
            self._cyclers = {}
            self._cycler_creation_lock = Lock()
            self._initialized = True
            print(f"[IpManager] Initialized with {len(self.ips)} IPs from '{self.config_file}': {self.ips}")

    def _load_ips(self):
        """從 JSON 設定檔中讀取 IP 列表。"""
        if not os.path.exists(self.config_file):
            print(f"[IpManager] Error: Config file '{self.config_file}' not found.")
            return []
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            ips = data.get("source_ips", [])
            if not isinstance(ips, list) or not all(isinstance(ip, str) for ip in ips):
                raise TypeError("'source_ips' must be a list of strings.")
            return [ip.strip() for ip in ips if ip.strip()]
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"[IpManager] Error: Invalid format in '{self.config_file}': {e}")
            return []

    def get_ip(self, user_class_name: str):
        """
        根據 User 的類別名稱，獲取下一個 IP。
        每種類型的 User 都有自己獨立的 IP 循環。
        """
        if user_class_name not in self._cyclers:
            # 如果這個 User 類型的 IP 循環器還不存在，就創建一個新的
            with self._cycler_creation_lock:
                # 再次檢查，防止多個執行緒同時創建同一個循環器
                if user_class_name not in self._cyclers:
                    print(f"[IpManager] Creating new IP cycler for '{user_class_name}'")
                    self._cyclers[user_class_name] = {
                        "cycler": itertools.cycle(self.ips),
                        "lock": Lock()
                    }
        
        # 獲取該 User 類型專屬的循環器和鎖
        cycler_info = self._cyclers[user_class_name]
        
        # 在該循環器的鎖保護下，獲取下一個 IP
        with cycler_info["lock"]:
            return next(cycler_info["cycler"])

# 導出一個 get_source_ip 函數，方便 locustfile 使用
def get_source_ip(user_class_name: str):
    """
    根據 User 類別名稱獲取一個來源 IP 位址。
    """
    manager = SourceIpManager()
    return manager.get_ip(user_class_name)
