#!/bin/bash

# 為 ueTun interfaces 設置 policy routing
# 解決當應用程序指定 source IP 時，封包無法正確路由到對應 interface 的問題

# 顯示使用說明
usage() {
    echo "Usage: sudo $0 [-d]"
    echo
    echo "Options:"
    echo "  (no option)  設置 policy routing 規則"
    echo "  -d           刪除所有 policy routing 規則"
    echo
    exit 1
}

# 刪除 policy routing 規則
delete_policy_routing() {
    echo "=========================================="
    echo "刪除 ueTun interface policy routing"
    echo "=========================================="
    echo

    # 刪除所有 10.60.100.x 的 policy routing 規則
    echo "[1] 刪除 policy routing 規則..."
    DELETED_COUNT=0
    
    # 查找所有 from 10.60.100.x 的規則
    while read -r line; do
        if [[ $line =~ from[[:space:]]+([0-9.]+)[[:space:]]+lookup[[:space:]]+([0-9]+) ]]; then
            IP="${BASH_REMATCH[1]}"
            TABLE="${BASH_REMATCH[2]}"
            
            echo "  🗑️  刪除規則: from $IP lookup $TABLE"
            ip rule del from $IP lookup $TABLE 2>/dev/null
            DELETED_COUNT=$((DELETED_COUNT + 1))
        fi
    done < <(ip rule show | grep "from 10.60.100\.")
    
    if [ $DELETED_COUNT -eq 0 ]; then
        echo "  ℹ️  沒有找到需要刪除的規則"
    else
        echo "  ✅ 已刪除 $DELETED_COUNT 條規則"
    fi
    echo

    # 清空路由表 (只清空我們使用的表 100-109，以及最多到 150)
    echo "[2] 清空相關路由表..."
    FLUSHED_COUNT=0
    
    # 只清理我們創建的路由表，從已刪除的規則中提取表編號
    for TABLE_ID in {100..150}; do
        # 檢查路由表是否包含 ueTun 相關的路由
        if ip route show table $TABLE_ID 2>/dev/null | grep -q "dev ueTun"; then
            echo "  🗑️  清空路由表 $TABLE_ID (包含 ueTun 路由)"
            ip route flush table $TABLE_ID 2>/dev/null
            FLUSHED_COUNT=$((FLUSHED_COUNT + 1))
        fi
    done
    
    if [ $FLUSHED_COUNT -eq 0 ]; then
        echo "  ℹ️  沒有找到需要清空的 ueTun 路由表"
    else
        echo "  ✅ 已清空 $FLUSHED_COUNT 個路由表"
    fi
    echo

    # 刷新路由緩存
    echo "[3] 刷新路由緩存..."
    ip route flush cache
    echo "✅ 完成"
    echo

    echo "=========================================="
    echo "所有 policy routing 規則已刪除"
    echo "=========================================="
    echo
}

# 設置 policy routing 規則
setup_policy_routing() {
    echo "=========================================="
    echo "設置 ueTun interface policy routing"
    echo "=========================================="
    echo

    # 檢查是否有 sudo 權限
    if [ "$EUID" -ne 0 ]; then 
        echo "請使用 sudo 執行此腳本"
        echo "Usage: sudo $0"
        exit 1
    fi

    # 獲取所有 ueTun interface 及其 IP
    echo "[1] 掃描 ueTun interfaces..."
    UE_INTERFACES=$(ip addr show | grep -oP 'ueTun\d+' | sort -u)

    if [ -z "$UE_INTERFACES" ]; then
        echo "❌ 沒有找到任何 ueTun interface"
        exit 1
    fi

    echo "找到以下 ueTun interfaces:"
    echo "$UE_INTERFACES" | sed 's/^/  - /'
    echo

    # 為每個 ueTun interface 添加路由規則
    echo "[2] 為每個 interface 添加 policy routing 規則..."
    echo

    for iface in $UE_INTERFACES; do
        # 獲取該 interface 的 IP 地址
        IP=$(ip -4 addr show $iface | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
        
        if [ -z "$IP" ]; then
            echo "⚠️  $iface: 沒有找到 IPv4 地址，跳過"
            continue
        fi
        
        # 提取 interface 編號（例如：ueTun0 -> 0）
        IFACE_NUM=$(echo $iface | grep -oP '\d+$')
        
        # 使用不同的路由表編號（100 + interface 編號）
        # 例如：ueTun0 -> table 100, ueTun1 -> table 101
        TABLE_ID=$((100 + IFACE_NUM))
        
        echo "處理 $iface (IP: $IP, Table: $TABLE_ID)"
        
        # 檢查路由表是否已經存在
        if ip rule show | grep -q "from $IP lookup $TABLE_ID"; then
            echo "  ℹ️  規則已存在，刪除舊規則..."
            ip rule del from $IP lookup $TABLE_ID 2>/dev/null
        fi
        
        # 檢查路由表中是否已有路由
        if ip route show table $TABLE_ID | grep -q default; then
            echo "  ℹ️  路由表已存在，清空..."
            ip route flush table $TABLE_ID
        fi
        
        # 添加 policy routing 規則：來自此 IP 的封包查詢特定路由表
        echo "  ➕ 添加規則: from $IP lookup table $TABLE_ID"
        ip rule add from $IP lookup $TABLE_ID
        
        # 在該路由表中添加 default route 經過該 interface
        # 注意：這裡假設封包會被 free5GC-UE 正確處理，所以只需要指定 dev
        echo "  ➕ 添加路由: default dev $iface (table $TABLE_ID)"
        ip route add default dev $iface table $TABLE_ID
        
        echo "  ✅ $iface 配置完成"
        echo
    done

    # 刷新路由緩存
    echo "[3] 刷新路由緩存..."
    ip route flush cache
    echo "✅ 完成"
    echo

    # 顯示當前配置
    echo "=========================================="
    echo "當前 Policy Routing 配置"
    echo "=========================================="
    echo
    echo "Policy Rules:"
    ip rule show | grep -E "from 10\.60\.100\."
    echo
    echo "路由表範例 (table 100):"
    ip route show table 100
    echo

    # 測試配置
    echo "=========================================="
    echo "測試配置"
    echo "=========================================="
    echo

    # 測試第一個 IP
    FIRST_IP=$(ip addr show ueTun0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)

    if [ -n "$FIRST_IP" ]; then
        echo "測試從 $FIRST_IP ping 8.8.8.8..."
        if ping -I $FIRST_IP -c 2 -W 2 8.8.8.8 >/dev/null 2>&1; then
            echo "✅ Ping 測試成功！Policy routing 配置正確"
        else
            echo "❌ Ping 測試失敗"
            echo "請檢查 free5GC-UE 的配置"
        fi
    else
        echo "⚠️  無法找到 ueTun0 的 IP，跳過測試"
    fi

    echo
    echo "=========================================="
    echo "配置完成"
    echo "=========================================="
    echo
    echo "注意："
    echo "1. 此配置在系統重啟後會丟失"
    echo "2. 如果 free5GC-UE 重新創建 interface，需要重新執行此腳本"
    echo "3. 可以將此腳本加入開機啟動或 systemd service"
    echo "4. 如需刪除規則，執行: sudo $0 -d"
    echo
}

# 主程序
# 檢查是否有 sudo 權限
if [ "$EUID" -ne 0 ]; then 
    echo "請使用 sudo 執行此腳本"
    usage
fi

# 解析命令行參數
case "${1:-}" in
    -d)
        delete_policy_routing
        ;;
    -h|--help)
        usage
        ;;
    "")
        setup_policy_routing
        ;;
    *)
        echo "錯誤: 未知的選項 '$1'"
        echo
        usage
        ;;
esac
