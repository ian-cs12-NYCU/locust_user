#!/bin/bash
# 协议切换脚本

CONFIG_FILE="./profiles/config-users.json"
LOCUST_CONF="./locust.conf"

show_usage() {
    echo "用法: $0 [http|https]"
    echo ""
    echo "快速切换 Locust 使用的协议"
    echo ""
    echo "选项:"
    echo "  http    - 切换到 HTTP 协议"
    echo "  https   - 切换到 HTTPS 协议"
    echo "  status  - 显示当前协议配置"
    echo ""
    exit 1
}

show_status() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "当前协议配置"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [ -f "$CONFIG_FILE" ]; then
        echo "📋 config-users.json:"
        grep -o '"protocol": "[^"]*"' "$CONFIG_FILE" | sed 's/"protocol": /  /' | sort | uniq -c
        echo ""
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

switch_protocol() {
    local protocol=$1
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "切换协议到: $protocol"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 备份配置文件
    if [ -f "$CONFIG_FILE" ]; then
        cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
        echo "✅ 已备份配置文件: ${CONFIG_FILE}.backup"
    fi
    
    echo ""
    
    # 更新 config-users.json
    if [ -f "$CONFIG_FILE" ]; then
        sed -i 's/"protocol": "http"/"protocol": "'"$protocol"'"/g' "$CONFIG_FILE"
        sed -i 's/"protocol": "https"/"protocol": "'"$protocol"'"/g' "$CONFIG_FILE"
        echo "✅ 已更新: $CONFIG_FILE"
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "协议切换完成！"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 显示新配置
    show_status
}

# 主程序
if [ $# -eq 0 ]; then
    show_usage
fi

case "$1" in
    http)
        switch_protocol "http"
        ;;
    https)
        switch_protocol "https"
        ;;
    status)
        show_status
        ;;
    *)
        echo "❌ 错误: 未知的协议 '$1'"
        echo ""
        show_usage
        ;;
esac
