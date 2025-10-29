#!/usr/bin/env python3
"""
Target Server Manager 測試腳本

用途：驗證 target_server.py 的功能是否正常運作
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.target_server import TargetServerManager, get_target_servers, get_random_target_server


def test_initialization():
    """測試管理器初始化"""
    print("=" * 60)
    print("測試 1: 管理器初始化")
    print("=" * 60)
    
    try:
        manager = TargetServerManager()
        print(f"✅ 管理器初始化成功")
        print(f"   載入子網段數量: {len(manager.subnets)}")
        print(f"   總 IP 地址數量: {len(manager.ip_pools)}")
        
        # 顯示每個子網段的資訊
        for subnet_config in manager.subnets:
            print(f"   - {subnet_config['subnet']}: 配重 {subnet_config['weight']}")
        
        return True
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        return False


def test_get_target_servers():
    """測試獲取目標伺服器列表"""
    print("\n" + "=" * 60)
    print("測試 2: 獲取目標伺服器列表")
    print("=" * 60)
    
    test_cases = [
        ("SocialUser", 2),
        ("VideoUser", 1),
        ("DnsLoad", 3),
        ("TestUser", 5),
    ]
    
    all_passed = True
    for user_class, count in test_cases:
        try:
            servers = get_target_servers(user_class, count)
            if len(servers) == count:
                print(f"✅ {user_class} (請求 {count} 個): {servers}")
            else:
                print(f"⚠️  {user_class} (請求 {count} 個, 實際獲得 {len(servers)} 個): {servers}")
        except Exception as e:
            print(f"❌ {user_class} 測試失敗: {e}")
            all_passed = False
    
    return all_passed


def test_random_target_server():
    """測試隨機獲取單一伺服器"""
    print("\n" + "=" * 60)
    print("測試 3: 隨機獲取單一伺服器")
    print("=" * 60)
    
    try:
        # 測試多次以查看隨機性
        servers = []
        for i in range(10):
            server = get_random_target_server("TestUser")
            servers.append(server)
        
        print(f"✅ 10 次隨機選擇結果:")
        for i, server in enumerate(servers, 1):
            print(f"   {i:2d}. {server}")
        
        # 統計不同 IP 的數量
        unique_servers = set(servers)
        print(f"\n   不重複的 IP 數量: {len(unique_servers)}")
        
        return True
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_weight_distribution():
    """測試配重分布"""
    print("\n" + "=" * 60)
    print("測試 4: 配重分布測試")
    print("=" * 60)
    
    try:
        # 進行大量選擇以驗證配重
        from collections import Counter
        selections = []
        
        num_selections = 10000
        print(f"進行 {num_selections} 次選擇...")
        
        for _ in range(num_selections):
            server = get_random_target_server("TestUser")
            # 提取子網段 (前三個八位元組)
            subnet_prefix = '.'.join(server.split('.')[:3]) + '.0'
            selections.append(subnet_prefix)
        
        # 統計每個子網段的選中次數
        counter = Counter(selections)
        
        print(f"\n子網段分布統計:")
        total = sum(counter.values())
        for subnet, count in sorted(counter.items()):
            percentage = (count / total) * 100
            bar = '█' * int(percentage / 2)
            print(f"   {subnet}/24: {count:5d} 次 ({percentage:5.2f}%) {bar}")
        
        return True
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_thread_safety():
    """測試執行緒安全性"""
    print("\n" + "=" * 60)
    print("測試 5: 執行緒安全性")
    print("=" * 60)
    
    try:
        import threading
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for _ in range(100):
                    servers = get_target_servers(f"Worker{worker_id}", 3)
                    results.append((worker_id, servers))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # 建立 10 個執行緒同時請求
        threads = []
        num_threads = 10
        
        print(f"啟動 {num_threads} 個執行緒同時請求...")
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # 等待所有執行緒完成
        for t in threads:
            t.join()
        
        if errors:
            print(f"❌ 發現 {len(errors)} 個錯誤:")
            for worker_id, error in errors[:5]:  # 只顯示前 5 個錯誤
                print(f"   Worker {worker_id}: {error}")
            return False
        else:
            print(f"✅ 所有 {len(results)} 次請求成功完成")
            print(f"   無併發錯誤")
            return True
            
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_edge_cases():
    """測試邊界情況"""
    print("\n" + "=" * 60)
    print("測試 6: 邊界情況測試")
    print("=" * 60)
    
    test_cases = [
        ("請求 0 個伺服器", "EdgeUser", 0),
        ("請求負數伺服器", "EdgeUser", -1),
        ("請求超大數量", "EdgeUser", 1000),
    ]
    
    for test_name, user_class, count in test_cases:
        try:
            servers = get_target_servers(user_class, count)
            print(f"✅ {test_name}: 返回 {len(servers)} 個伺服器")
        except Exception as e:
            print(f"⚠️  {test_name}: 拋出異常 - {e}")


def main():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("Target Server Manager 功能測試")
    print("=" * 60)
    
    tests = [
        ("初始化", test_initialization),
        ("獲取伺服器列表", test_get_target_servers),
        ("隨機選擇", test_random_target_server),
        ("配重分布", test_weight_distribution),
        ("執行緒安全", test_thread_safety),
        ("邊界情況", test_edge_cases),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} 測試發生未預期的錯誤: {e}")
            results.append((test_name, False))
    
    # 總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
    
    print(f"\n總計: {passed}/{total} 測試通過 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 所有測試通過！系統運作正常。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 個測試失敗，請檢查配置和程式碼。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
