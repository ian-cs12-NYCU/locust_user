``` 
    source ./.venv/bin/activate
    locust --config ./locust.conf 
```

## Health Check
```
    curl -v http://10.201.0.123/
    curl -v http://10.201.0.123/feed?since=123456 -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'
    curl -v http://10.201.0.123/video/720p/seg-7.ts -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'
    curl -v http://10.201.0.123/video/720p/video-1/playlist.m3u8 -o /dev/null -s -w 'code=%{http_code} size_download=%{size_download} time_total=%{time_total}\n'

```

MQTT Check
```
    mosquitto_sub -h 10.201.0.123 -p 1883 -t "hello world/reply" -v 
    mosquitto_pub -h 10.201.0.123 -p 1883 -t "hello world" -v -m "test message from script"
```

## Config
``` 
    [
        {
            "user_class_name": "SocialUser", 
            "weight": 3
        },
        {
            "user_class_name": "MqttUser", 
            "fixed_count": 75, 
            "mqtt_host": "10.60.0.2", 
            "mqtt_port": 1883
        },
        {

        }
    ]
```

### 快速切換要加速的 user 類型（三種方式）

換 JSON 檔：config-users = ./profiles/mqtt_burst.json（最直覺，適合 headless）。

用 weight：把目標類的 "weight": 大數值，其餘小數值；同總人數下它會被優先補滿。

互動調整（非 headless）：啟動加 --class-picker，在 UI 直接選 class 與人數/權重。