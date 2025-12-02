# Locust User Load Testing

## Install

```bash
uv pip install -e .
```

## Run

```bash
source ./.venv/bin/activate
locust --config ./locust.conf
```

## 配置檔案

### profiles/config-users.json
定義 User 類型、權重和目標伺服器數量：
```json
[
  { 
    "user_class_name": "SocialUser", 
    "weight": 1,
    "host": "http://httpbin.org",
    "target_server_count": 2
  },
  { 
    "user_class_name": "VideoUser",  
    "weight": 1,
    "target_server_count": 1
  },
  {
    "user_class_name": "DnsLoad",
    "weight": 1,
    "dns_server": "10.201.0.180",
    "dns_port": 53,
    "target_server_count": 3
  }
]
```

### profiles/target.json
定義目標伺服器子網段和流量配重：
```json
{
  "target_subnets": [
    {
      "subnet": "10.201.0.0/28",
      "description": "Social服務子網段",
      "weight": 3,
      "user_types": ["SocialUser"]
    },
    {
      "subnet": "10.201.0.128/28",
      "description": "Video服務子網段",
      "weight": 2,
      "user_types": ["VideoUser"]
    },
    {
      "subnet": "10.201.0.144/28",
      "description": "通用服務子網段",
      "weight": 1,
      "user_types": ["SocialUser", "VideoUser", "DnsLoad"]
    }
  ]
}
```

**欄位說明**：
- `subnet`: 子網段（CIDR 格式）
- `weight`: 配重（數值越大，被選中機率越高）
- `user_types`: 允許使用此子網段的 User 類型列表（空陣列表示所有類型都可用）

### profiles/ips.json
定義來源 IP 地址池：
```json
{
  "source_ips": [
    "192.168.1.10",
    "192.168.1.11",
    "192.168.1.12"
  ]
}
```

## 功能說明

### Target Server 動態分配
- 每種 User 可配置目標伺服器數量 (`target_server_count`)
- 支援基於配重的隨機分配（`weight` 越大，被選中機率越高）
- **子網段專屬分配**：透過 `user_types` 指定哪些 User 可以使用特定子網段
  - 例如：VideoUser 只會從 Video 子網段中選擇目標伺服器
  - 通用子網段可設定多個 User 類型共用
- 每個 User 實例在執行時從分配到的伺服器列表中隨機選擇目標

### 測試
```bash
# 執行所有單元測試
python3 -m unittest utils/test_target_server.py -v

# 或使用 pytest (如果已安裝)
pytest utils/test_target_server.py -v
```

## Health Check## Health Check

### HTTP Service
```bash
curl -v http://10.201.0.123/
curl -v http://10.201.0.123/feed?since=123456 -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'
curl -v http://10.201.0.123/video/720p/seg-7.ts -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'
curl -v http://10.201.0.123/video/720p/video-1/playlist.m3u8 -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'
```

### MQTT Service
```bash
# Terminal 1 - Subscribe
mosquitto_sub -h 10.201.0.123 -p 1883 -t "hello world/reply" -v  

# Terminal 2 - Publish
mosquitto_pub -h 10.201.0.123 -p 1883 -t "hello world" -m "test message from script"
```

預期輸出：
```
hello world/reply {"ok": true, "echo": "hello world", "original_message": "test message from script"}
```

### DNS Service
```bash
dig @10.201.0.123 twitter.com A
```

## 快速切換 User 類型

### 方法 1: 切換 JSON 檔案
```bash
# 在 locust.conf 中修改
config-users = ./profiles/mqtt_burst.json
```

### 方法 2: 調整權重
在 `config-users.json` 中調整 `weight` 值，數值大的 User 會優先被建立

### 方法 3: UI 互動調整
```bash
locust --class-picker
```
在 UI 中直接選擇 User class 與人數/權重

### script

* quick_test.sh : 快速測試目標伺服器連通性
* setup_policy_routing.sh : 設定來源 IP 的 Policy Routing，當使用的 free-ran-ue 有支援 policy routing 時無需執行此腳本