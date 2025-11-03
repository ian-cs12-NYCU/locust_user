#!/usr/bin/env python3
"""
測試 IP 綁定功能的診斷腳本
用於檢查每個 UE 的 IP 是否能正確綁定並發送封包
"""

import socket
import requests
from requests_toolbelt.adapters.source import SourceAddressAdapter
import dns.message
import dns.rdatatype
import dns.query

def test_source_ip_binding(source_ip):
    """測試單個 source IP 的綁定功能"""
    print(f"\n{'='*60}")
    print(f"測試 IP: {source_ip}")
    print(f"{'='*60}")
    
    # 測試 1: Raw Socket 綁定
    print(f"[1] 測試 Raw Socket 綁定...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((source_ip, 0))
        sock.settimeout(2)
        print(f"    ✓ Socket 綁定成功: {source_ip}")
        sock.close()
    except Exception as e:
        print(f"    ✗ Socket 綁定失敗: {e}")
        return False
    
    # 測試 2: HTTP 請求綁定
    print(f"[2] 測試 HTTP 請求綁定...")
    try:
        session = requests.Session()
        adapter = SourceAddressAdapter((source_ip, 0))
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 測試連接到 httpbin.org
        response = session.get("http://httpbin.org/ip", timeout=5)
        if response.status_code == 200:
            print(f"    ✓ HTTP 請求成功: {response.status_code}")
            print(f"    返回內容: {response.json()}")
        else:
            print(f"    ⚠ HTTP 請求返回: {response.status_code}")
    except requests.exceptions.Timeout:
        print(f"    ✗ HTTP 請求超時")
        return False
    except Exception as e:
        print(f"    ✗ HTTP 請求失敗: {e}")
        return False
    
    # 測試 3: DNS 查詢綁定
    print(f"[3] 測試 DNS 查詢綁定...")
    try:
        q = dns.message.make_query('google.com', dns.rdatatype.A)
        response = dns.query.udp(q, '8.8.8.8', timeout=5, source=source_ip)
        if response.rcode() == dns.rcode.NOERROR:
            print(f"    ✓ DNS 查詢成功")
        else:
            print(f"    ⚠ DNS 查詢返回: {dns.rcode.to_text(response.rcode())}")
    except dns.exception.Timeout:
        print(f"    ✗ DNS 查詢超時")
        return False
    except Exception as e:
        print(f"    ✗ DNS 查詢失敗: {e}")
        return False
    
    print(f"{'='*60}")
    print(f"✓ IP {source_ip} 所有測試通過")
    return True

def test_all_ips():
    """測試前10個 IP"""
    ips_to_test = [f"10.60.100.{i}" for i in range(1, 11)]
    
    print(f"\n開始測試前 10 個 UE IP...")
    print(f"測試 IP 列表: {', '.join(ips_to_test)}\n")
    
    success_count = 0
    failed_ips = []
    
    for ip in ips_to_test:
        if test_source_ip_binding(ip):
            success_count += 1
        else:
            failed_ips.append(ip)
    
    print(f"\n{'='*60}")
    print(f"測試結果摘要")
    print(f"{'='*60}")
    print(f"總共測試: {len(ips_to_test)} 個 IP")
    print(f"成功: {success_count} 個")
    print(f"失敗: {len(failed_ips)} 個")
    
    if failed_ips:
        print(f"\n失敗的 IP 列表:")
        for ip in failed_ips:
            print(f"  - {ip}")
    
    return success_count, failed_ips

if __name__ == "__main__":
    success, failed = test_all_ips()
    
    if failed:
        print(f"\n⚠ 發現問題: {len(failed)} 個 IP 無法正常工作")
        print(f"請檢查這些 IP 的網路介面設定和路由規則")
        exit(1)
    else:
        print(f"\n✓ 所有 IP 測試通過!")
        exit(0)
