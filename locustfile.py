from locust import FastHttpUser, User, task, constant_pacing, constant_throughput, constant, events
from locust.contrib.mqtt import MqttUser, MqttClient
import random, os
import paho.mqtt.client as mqtt, os, time, random, json

class SocialUser(FastHttpUser):
    """社群互動用戶：快速、頻繁的請求"""
    wait_time = constant_throughput(1)  # 每秒 1 次 task（適合短時間 task）
    
    @task(6)  # 權重：社群
    def feed_scroll(self):
        # 圖片/短片混合
        self.client.get(f"/feed?since={random.randint(1, 1_000_000_000)}", name="SOCIAL:feed")
        # 小上傳（評論/按讚）
        if random.random()<0.3:
            self.client.post("/react", json={"pid":random.randint(1, 1_000_000)}, name="SOCIAL:react")
    
    @task(4)  # 其他：瀏覽/搜尋
    def browse(self):
        self.client.get("/", name="WEB:index")


class VideoUser(FastHttpUser):
    """影音串流用戶：長時間連續 session"""
    # 不設 wait_time，讓 session 內部的 sleep 自然控制節奏
    # 或用很長的間隔，例如：wait_time = constant(300)  # 每次 session 結束後等 5 分鐘
    
    @task
    def video_watch_session(self):
        # 1. 抓 playlist（模擬播放器初始化）
        video_id = random.randint(1, 10000)
        self.client.get(f"/video/720p/video-{video_id}/playlist.m3u8", name="VIDEO:playlist")
        
        # 2. 決定這次 session 要看幾段（模擬短/中/長影片或中途離開）
        # 假設每段 3 秒，60 段 = 3 分鐘，300 段 = 15 分鐘
        watch_segments = random.randint(10, 100)  # 可調整範圍
        
        # 3. 從某個起始 segment 開始連續抓取
        start_seg = random.randint(1, 1000)
        seg = start_seg
        
        for i in range(watch_segments):
            # 抓取當前 segment
            with self.client.get(
                f"/video/720p/seg-{seg}.ts", 
                name="VIDEO:hls_seg",
                catch_response=True
            ) as resp:
                if resp.status_code != 200:
                    resp.failure(f"Segment {seg} failed with status {resp.status_code}")
                    # 可選：遇到錯誤就中斷 session（模擬播放器停止）
                    if resp.status_code >= 500:
                        break
            
            # 4. 模擬 segment 播放時間 + 網路 jitter（2~4 秒）
            time.sleep(random.uniform(2.0, 4.0))
            seg += 1
            
            # 可選：模擬使用者中途跳出（5% 機率提前結束）
            if random.random() < 0.05:
                break



# 自定義 MqttClient 以便更好地追蹤和除錯
class IoTMqttClient(MqttClient):
    def _generate_event_name(self, event_type: str, qos: int, topic: str):
        # 使用更具描述性的事件名稱
        return f"mqtt:{event_type}:{qos}:{topic}"


class IoTUser(MqttUser):
    # 這些屬性都可以被 config-users 覆寫
    host = "10.201.0.123"     # MQTT broker
    port = 1883
    min_wait = 0.01        # 動態控制等待區間（可在 JSON 設）
    max_wait = 0.10
    
    # MQTT Topics
    publish_topic = "hello world"          # 發布的 topic
    subscribe_topic = "hello world/reply"  # 訂閱的 topic
    
    # 使用自定義的 MqttClient
    client_cls = IoTMqttClient
    
    # 統計收到的訊息數量
    received_count = 0

    # 讓等待時間可被 min/max 調整（JSON 改 min_wait/max_wait 即生效）
    def wait_time(self):
        return random.uniform(self.min_wait, self.max_wait)

    def on_start(self):
        """
        按照官方範例，使用 time.sleep 等待連線建立
        MqttUser 已經在 __init__ 中調用 connect_async 和 loop_start
        """
        # Debug: 印出連線資訊
        print(f"[IoTUser Debug] Original host setting: {self.host}:{self.port}")
        
        # 清理 host 中的 http:// 或 https:// 前綴
        # 這些前綴是給 HttpUser 用的，MQTT 不需要
        if isinstance(self.host, str):
            self.host = self.host.replace('http://', '').replace('https://', '')
        
        print(f"[IoTUser Debug] Cleaned host: {self.host}:{self.port}")
        print(f"[IoTUser Debug] Publish topic: {self.publish_topic}")
        print(f"[IoTUser Debug] Subscribe topic: {self.subscribe_topic}")
        
        # Workaround: 重新連線以確保使用正確的 host/port
        # 因為 MqttUser.__init__ 可能在 JSON 配置應用之前就執行了
        print(f"[IoTUser Debug] Reconnecting to ensure correct broker...")
        
        # 先停止 loop
        self.client.loop_stop()
        time.sleep(0.2)
        
        # 斷線
        self.client.disconnect()
        time.sleep(0.5)
        
        # 重新連線（使用清理後的 host）
        self.client.connect_async(host=self.host, port=self.port)
        
        # 重新啟動 loop
        self.client.loop_start()
        
        # 按照官方文檔建議，sleep 等待連線建立
        # 官方說明：這可能不是最正確的方式，更好的方法是使用 gevent.event.Event
        # 但對於範例來說這已經足夠好了
        print(f"[IoTUser Debug] Waiting 5 seconds for connection to establish...")
        time.sleep(5)
        
        # 檢查連線狀態並訂閱
        if self.client.is_connected():
            print(f"[IoTUser Debug] ✅ Connected successfully to {self.host}:{self.port}!")
            
            # 設置接收訊息的 callback
            def on_message(client, userdata, message):
                self.received_count += 1
                payload = message.payload.decode('utf-8', errors='ignore')
                print(f"[IoTUser Debug] 📬 Received #{self.received_count} on '{message.topic}': {payload}")
                
                # 手動觸發 Locust 事件以追蹤收到的訊息
                # 這樣 Locust UI 才會顯示統計
                self.environment.events.request.fire(
                    request_type="MQTT",
                    name=f"mqtt:receive:0:{message.topic}",
                    response_time=0,  # 接收訊息沒有延遲時間
                    response_length=len(message.payload),
                    exception=None,
                    context={}
                )
            
            self.client.on_message = on_message
            
            # 訂閱 reply topic
            result = self.client.subscribe(self.subscribe_topic)
            print(f"[IoTUser Debug] 📥 Subscribed to '{self.subscribe_topic}' - Result: {result}")
        else:
            print(f"[IoTUser Debug] ❌ Connection failed to {self.host}:{self.port} after 5 seconds")

    @task
    def say_hello(self):
        # 在發布前檢查連線狀態
        if not self.client.is_connected():
            print(f"[IoTUser Debug] ⚠️  Not connected, skipping publish")
            return
        
        print(f"[IoTUser Debug] 📤 Publishing to '{self.publish_topic}'")
        self.client.publish(self.publish_topic, b"hello world")
    
    def on_stop(self):
        """當用戶停止時顯示統計"""
        print(f"[IoTUser Debug] 📊 Total messages received: {self.received_count}")