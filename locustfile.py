from locust import FastHttpUser, User, task, constant_pacing, constant_throughput, constant, events
from locust.contrib.mqtt import MqttUser
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



class IoTUser(MqttUser):
    # 這些屬性都可以被 config-users 覆寫
    host = "127.0.0.1"     # MQTT broker
    port = 1883
    min_wait = 0.01        # 動態控制等待區間（可在 JSON 設）
    max_wait = 0.10
    connect_timeout = 5.0  # 連線等待上限（秒）

    # 讓等待時間可被 min/max 調整（JSON 改 min_wait/max_wait 即生效）
    def wait_time(self):
        return random.uniform(self.min_wait, self.max_wait)

    def on_start(self):
        # 等待連線就緒（取代固定 sleep）
        connected = False
        def _on_connect(client, userdata, flags, rc, properties=None):
            nonlocal connected
            connected = True
        try:
            self.client.on_connect = _on_connect
        except Exception:
            pass

        deadline = time.time() + float(self.connect_timeout)
        while not connected and time.time() < deadline:
            time.sleep(0.1)

    @task
    def say_hello(self):
        self.client.publish("hello/locust", b"hello world")