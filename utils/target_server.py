import json
import os
import random
import ipaddress
from threading import Lock
from pathlib import Path
from typing import List, Dict

class TargetServerManager:
    """
    目標伺服器管理器，根據設定檔中的子網和配重，
    為每個 User 實例動態分配目標伺服器列表。
    
    特性：
    1. 從 profiles/target.json 讀取子網配置和配重
    2. 根據配重進行加權隨機選擇
    3. 為每個 User 類型提供獨立的目標伺服器分配
    4. 執行緒安全的單例模式
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

            print(f"[TargetServerManager] Initializing...")
            base_dir = Path(__file__).parent.parent
            self.config_file = base_dir / 'profiles' / 'target.json'
            self.subnets = self._load_subnets()
            
            if not self.subnets:
                raise ValueError(f"Subnet list in '{self.config_file}' is empty or not found.")
            
            # 建立所有可用的 IP 地址池和對應的配重
            self.ip_pools = []  # [(ip_address, weight), ...]
            self._build_ip_pools()
            
            self._allocation_lock = Lock()
            self._initialized = True
            print(f"[TargetServerManager] Initialized with {len(self.subnets)} subnets, "
                  f"total {len(self.ip_pools)} available IPs")

    def _load_subnets(self) -> List[Dict]:
        """從 JSON 設定檔中讀取子網列表。"""
        if not os.path.exists(self.config_file):
            print(f"[TargetServerManager] Error: Config file '{self.config_file}' not found.")
            return []
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            subnets = data.get("target_subnets", [])
            
            if not isinstance(subnets, list):
                raise TypeError("'target_subnets' must be a list.")
            
            # 驗證每個子網的格式
            for subnet in subnets:
                if not all(k in subnet for k in ['subnet', 'weight']):
                    raise ValueError("Each subnet must have 'subnet' and 'weight' fields.")
                if not isinstance(subnet['weight'], (int, float)) or subnet['weight'] <= 0:
                    raise ValueError(f"Weight must be a positive number for subnet {subnet['subnet']}")
            
            return subnets
            
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            print(f"[TargetServerManager] Error: Invalid format in '{self.config_file}': {e}")
            return []

    def _build_ip_pools(self):
        """根據子網配置建立 IP 地址池。"""
        for subnet_config in self.subnets:
            try:
                subnet = ipaddress.ip_network(subnet_config['subnet'], strict=False)
                weight = subnet_config['weight']
                
                # 獲取子網中所有可用的主機 IP（排除網路地址和廣播地址）
                # 對於 /28 子網，這會給出 14 個可用 IP
                for ip in subnet.hosts():
                    self.ip_pools.append((str(ip), weight))
                
                print(f"[TargetServerManager] Loaded subnet {subnet_config['subnet']} "
                      f"with weight {weight}, {subnet.num_addresses - 2} hosts")
                      
            except (ValueError, KeyError) as e:
                print(f"[TargetServerManager] Error processing subnet {subnet_config.get('subnet', 'unknown')}: {e}")
                continue

    def get_target_servers(self, user_class_name: str, count: int) -> List[str]:
        """
        為指定的 User 類型分配目標伺服器列表。
        
        Args:
            user_class_name: User 類別名稱（用於日誌記錄）
            count: 需要的目標伺服器數量
            
        Returns:
            目標伺服器 IP 地址列表
        """
        if count <= 0:
            return []
        
        if not self.ip_pools:
            print(f"[TargetServerManager] Warning: No IPs available for {user_class_name}")
            return []
        
        with self._allocation_lock:
            # 使用加權隨機選擇
            # 如果請求的數量超過可用 IP 數量，則允許重複
            selected_ips = []
            
            # 準備加權選擇的數據
            ips = [ip for ip, _ in self.ip_pools]
            weights = [weight for _, weight in self.ip_pools]
            
            # 如果請求數量小於等於可用 IP 數量，嘗試不重複選擇
            if count <= len(ips):
                # 使用加權隨機選擇，不重複
                selected_ips = random.choices(ips, weights=weights, k=count)
                # 移除重複（如果有的話）並補充
                selected_ips = list(dict.fromkeys(selected_ips))
                while len(selected_ips) < count:
                    additional = random.choices(ips, weights=weights, k=count - len(selected_ips))
                    selected_ips.extend(additional)
                    selected_ips = list(dict.fromkeys(selected_ips))
                selected_ips = selected_ips[:count]
            else:
                # 如果請求數量超過可用 IP，允許重複
                selected_ips = random.choices(ips, weights=weights, k=count)
            
            print(f"[TargetServerManager] Allocated {len(selected_ips)} target servers "
                  f"for {user_class_name}: {selected_ips}")
            
            return selected_ips

    def get_random_target_server(self, user_class_name: str) -> str:
        """
        為指定的 User 類型隨機返回一個目標伺服器。
        適用於動態選擇場景。
        
        Args:
            user_class_name: User 類別名稱（用於日誌記錄）
            
        Returns:
            單個目標伺服器 IP 地址
        """
        if not self.ip_pools:
            print(f"[TargetServerManager] Warning: No IPs available for {user_class_name}")
            return ""
        
        with self._allocation_lock:
            ips = [ip for ip, _ in self.ip_pools]
            weights = [weight for _, weight in self.ip_pools]
            selected_ip = random.choices(ips, weights=weights, k=1)[0]
            
            return selected_ip


# 導出便利函數
def get_target_servers(user_class_name: str, count: int) -> List[str]:
    """
    根據 User 類別名稱獲取指定數量的目標伺服器列表。
    
    Args:
        user_class_name: User 類別名稱
        count: 需要的目標伺服器數量
        
    Returns:
        目標伺服器 IP 地址列表
    """
    manager = TargetServerManager()
    return manager.get_target_servers(user_class_name, count)


def get_random_target_server(user_class_name: str) -> str:
    """
    根據 User 類別名稱隨機獲取一個目標伺服器。
    
    Args:
        user_class_name: User 類別名稱
        
    Returns:
        單個目標伺服器 IP 地址
    """
    manager = TargetServerManager()
    return manager.get_random_target_server(user_class_name)
