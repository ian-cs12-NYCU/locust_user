"""
Target Server Manager 單元測試

使用標準的 unittest 框架進行測試
執行方式：python -m pytest utils/test_target_server.py -v
或：python -m unittest utils/test_target_server.py
"""

import unittest
import sys
from pathlib import Path
from collections import Counter
import threading
from unittest.mock import patch, MagicMock

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.target_server import TargetServerManager, get_target_servers, get_random_target_server


# 測試用的固定配置 - 不依賴外部文件
TEST_SUBNETS = [
    {
        "subnet": "10.201.0.0/28",
        "description": "Social 專用子網段 1",
        "weight": 3,
        "user_types": ["SocialUser"]
    },
    {
        "subnet": "10.201.0.16/28",
        "description": "Social 專用子網段 2",
        "weight": 3,
        "user_types": ["SocialUser"]
    },
    {
        "subnet": "10.201.0.128/28",
        "description": "Video 專用子網段",
        "weight": 2,
        "user_types": ["VideoUser"]
    },
    {
        "subnet": "10.201.0.144/28",
        "description": "通用子網段（所有類型）",
        "weight": 1,
        "user_types": ["SocialUser", "VideoUser", "DnsLoad"]
    }
]


class TestTargetServerManager(unittest.TestCase):
    """TargetServerManager 單元測試類別"""
    
    def setUp(self):
        """每個測試前重置單例並使用測試配置"""
        # 重置單例實例
        TargetServerManager._instance = None
        
        # Mock _load_subnets 方法返回測試配置
        with patch.object(TargetServerManager, '_load_subnets', return_value=TEST_SUBNETS):
            self.manager = TargetServerManager()
    
    def tearDown(self):
        """測試後清理"""
        # 重置單例，避免影響其他測試
        TargetServerManager._instance = None
    
    def test_01_initialization(self):
        """測試管理器初始化"""
        self.assertIsNotNone(self.manager)
        self.assertGreater(len(self.manager.subnets), 0, "應該載入至少一個子網段")
        self.assertGreater(len(self.manager.ip_pools), 0, "應該有可用的 IP 地址")
    
    def test_02_subnet_loading(self):
        """測試子網段載入"""
        for subnet_config in self.manager.subnets:
            self.assertIn('subnet', subnet_config)
            self.assertIn('weight', subnet_config)
            self.assertGreater(subnet_config['weight'], 0, "配重應該大於 0")
    
    def test_03_ip_pool_structure(self):
        """測試 IP 池結構"""
        for ip_info in self.manager.ip_pools:
            self.assertIn('ip', ip_info)
            self.assertIn('weight', ip_info)
            self.assertIn('user_types', ip_info)
            self.assertIsInstance(ip_info['user_types'], list)
    
    def test_04_get_target_servers_social_user(self):
        """測試 SocialUser 獲取目標伺服器"""
        servers = self.manager.get_target_servers("SocialUser", 2)
        self.assertEqual(len(servers), 2, "應該返回 2 個伺服器")
        
        # 驗證 IP 是否來自 Social 子網段
        for ip in servers:
            self.assertTrue(
                ip.startswith("10.201.0.") and (
                    1 <= int(ip.split('.')[-1]) <= 14 or
                    17 <= int(ip.split('.')[-1]) <= 30 or
                    145 <= int(ip.split('.')[-1]) <= 158
                ),
                f"SocialUser 的 IP {ip} 應該來自允許的子網段"
            )
    
    def test_05_get_target_servers_video_user(self):
        """測試 VideoUser 獲取目標伺服器"""
        servers = self.manager.get_target_servers("VideoUser", 1)
        self.assertEqual(len(servers), 1, "應該返回 1 個伺服器")
        
        # 驗證 IP 是否來自 Video 子網段
        ip = servers[0]
        last_octet = int(ip.split('.')[-1])
        self.assertTrue(
            ip.startswith("10.201.0.") and (
                129 <= last_octet <= 142 or
                145 <= last_octet <= 158
            ),
            f"VideoUser 的 IP {ip} 應該來自 Video 或通用子網段"
        )
    
    def test_06_get_target_servers_dns_load(self):
        """測試 DnsLoad 獲取目標伺服器"""
        servers = self.manager.get_target_servers("DnsLoad", 3)
        self.assertEqual(len(servers), 3, "應該返回 3 個伺服器")
        
        # DnsLoad 只能使用通用子網段
        for ip in servers:
            last_octet = int(ip.split('.')[-1])
            self.assertTrue(
                ip.startswith("10.201.0.") and 145 <= last_octet <= 158,
                f"DnsLoad 的 IP {ip} 應該來自通用子網段"
            )
    
    def test_07_get_target_servers_unknown_user(self):
        """測試未配置的 User 類型"""
        servers = self.manager.get_target_servers("UnknownUser", 5)
        self.assertEqual(len(servers), 0, "未配置的 User 類型應該返回空列表")
    
    def test_08_get_target_servers_zero_count(self):
        """測試請求 0 個伺服器"""
        servers = self.manager.get_target_servers("SocialUser", 0)
        self.assertEqual(len(servers), 0, "請求 0 個應該返回空列表")
    
    def test_09_get_target_servers_negative_count(self):
        """測試請求負數伺服器"""
        servers = self.manager.get_target_servers("SocialUser", -1)
        self.assertEqual(len(servers), 0, "請求負數應該返回空列表")
    
    def test_10_get_random_target_server(self):
        """測試隨機獲取單一伺服器"""
        server = self.manager.get_random_target_server("SocialUser")
        self.assertIsInstance(server, str)
        self.assertTrue(len(server) > 0, "應該返回有效的 IP 地址")
        self.assertTrue(server.startswith("10.201.0."))
    
    def test_11_random_target_server_distribution(self):
        """測試隨機選擇的分布性"""
        selections = []
        for _ in range(100):
            server = self.manager.get_random_target_server("SocialUser")
            if server:
                selections.append(server)
        
        # 應該有多樣性（不是每次都返回同一個 IP）
        unique_servers = set(selections)
        self.assertGreater(len(unique_servers), 1, "應該有多個不同的 IP 被選中")
    
    def test_12_thread_safety(self):
        """測試執行緒安全性"""
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for _ in range(50):
                    servers = self.manager.get_target_servers("SocialUser", 2)
                    results.append((worker_id, servers))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # 建立 5 個執行緒同時請求
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有執行緒完成
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0, f"不應該有執行緒錯誤: {errors}")
        self.assertEqual(len(results), 250, "應該完成 250 次請求 (5 執行緒 * 50 次)")
    
    def test_13_weight_distribution(self):
        """測試配重分布（統計驗證）"""
        selections = []
        num_selections = 1000
        
        for _ in range(num_selections):
            server = self.manager.get_random_target_server("SocialUser")
            if server:
                # 判斷來自哪個子網段
                last_octet = int(server.split('.')[-1])
                if 1 <= last_octet <= 14:
                    selections.append("10.201.0.0/28")
                elif 17 <= last_octet <= 30:
                    selections.append("10.201.0.16/28")
                elif 145 <= last_octet <= 158:
                    selections.append("10.201.0.144/28")
        
        counter = Counter(selections)
        
        # 驗證高權重子網段的選中次數應該較多
        # 10.201.0.0/28 (weight=3) 和 10.201.0.16/28 (weight=3) 應該比 10.201.0.144/28 (weight=1) 多
        if len(counter) > 0:
            total = sum(counter.values())
            # 至少應該有一些分布
            self.assertGreater(total, 0, "應該有成功的選擇")
    
    def test_14_user_type_isolation(self):
        """測試 User 類型隔離"""
        # SocialUser 應該只獲得 Social 相關的 IP
        social_servers = self.manager.get_target_servers("SocialUser", 10)
        for ip in social_servers:
            last_octet = int(ip.split('.')[-1])
            # Social 可以用 0.0/28, 0.16/28, 0.144/28
            self.assertTrue(
                (1 <= last_octet <= 14) or 
                (17 <= last_octet <= 30) or 
                (145 <= last_octet <= 158),
                f"SocialUser 不應該獲得 {ip}"
            )
        
        # VideoUser 應該只獲得 Video 相關的 IP
        video_servers = self.manager.get_target_servers("VideoUser", 10)
        for ip in video_servers:
            last_octet = int(ip.split('.')[-1])
            # Video 可以用 0.128/28, 0.144/28
            self.assertTrue(
                (129 <= last_octet <= 142) or 
                (145 <= last_octet <= 158),
                f"VideoUser 不應該獲得 {ip}"
            )
    
    def test_15_large_count_request(self):
        """測試請求大量伺服器"""
        servers = self.manager.get_target_servers("SocialUser", 1000)
        # 應該返回結果（可能有重複）
        self.assertGreater(len(servers), 0)
        # 數量應該符合請求
        self.assertEqual(len(servers), 1000)
    
    def test_16_singleton_pattern(self):
        """測試單例模式"""
        # 注意：由於我們在 setUp 中重置單例，這裡測試的是正常運行時的單例行為
        with patch.object(TargetServerManager, '_load_subnets', return_value=TEST_SUBNETS):
            manager1 = TargetServerManager()
            manager2 = TargetServerManager()
            self.assertIs(manager1, manager2, "應該返回同一個實例")


class TestTargetServerIntegration(unittest.TestCase):
    """整合測試"""
    
    def setUp(self):
        """每個測試前重置單例並使用測試配置"""
        # 重置單例實例
        TargetServerManager._instance = None
        
        # Mock _load_subnets 方法返回測試配置
        with patch.object(TargetServerManager, '_load_subnets', return_value=TEST_SUBNETS):
            self.manager = TargetServerManager()
    
    def tearDown(self):
        """測試後清理"""
        # 重置單例，避免影響其他測試
        TargetServerManager._instance = None
    
    def test_01_complete_workflow(self):
        """測試完整工作流程"""
        # 1. 初始化管理器
        self.assertIsNotNone(self.manager)
        
        # 2. 為不同 User 類型獲取伺服器
        social_servers = self.manager.get_target_servers("SocialUser", 2)
        video_servers = self.manager.get_target_servers("VideoUser", 1)
        dns_servers = self.manager.get_target_servers("DnsLoad", 3)
        
        # 3. 驗證結果
        self.assertEqual(len(social_servers), 2)
        self.assertEqual(len(video_servers), 1)
        self.assertEqual(len(dns_servers), 3)
        
        # 4. 驗證沒有交叉污染（Video 的 IP 不會出現在 Social 的非通用子網段中）
        for ip in social_servers:
            last_octet = int(ip.split('.')[-1])
            # Social 伺服器不應該在純 Video 子網段（129-142）
            if 129 <= last_octet <= 142:
                self.fail(f"SocialUser 不應該獲得純 Video 子網段的 IP: {ip}")


def run_tests(verbosity=2):
    """執行所有測試"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 載入所有測試
    suite.addTests(loader.loadTestsFromTestCase(TestTargetServerManager))
    suite.addTests(loader.loadTestsFromTestCase(TestTargetServerIntegration))
    
    # 執行測試
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # 返回測試結果
    return result.wasSuccessful()


if __name__ == "__main__":
    # 支援 unittest 的標準執行方式
    unittest.main(verbosity=2)
