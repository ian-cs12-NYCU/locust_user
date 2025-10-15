from locust import FastHttpUser, User, task, constant_pacing, constant_throughput, constant, events
from locust.contrib.mqtt import MqttUser
import random, os
import paho.mqtt.client as mqtt, os, time, random, json

import warnings
# ignore paho-mqtt deprecation warnings
warnings.filterwarnings(
    "ignore",
    message=r".*Callback API version 1 is deprecated.*",
    category=DeprecationWarning,
    module=r"paho\.mqtt\..*",
)

class SocialUser(FastHttpUser):
    wait_time = constant_throughput(5)  
    @task(6)  # 權重：社群
    def feed_scroll(self):
        # 圖片/短片混合
        self.client.get(f"/feed?since={random.randint(1, 1_000_000_000)}", name="SOCIAL:feed")
        # 小上傳（評論/按讚）
        if random.random()<0.3:
            self.client.post("/react", json={"pid":random.randint(1, 1_000_000)}, name="SOCIAL:react")
    @task(5)  # 權重：影音（HLS 段檔）
    def video_hls(self):
        seg = random.randint(1, 1000)
        self.client.get(f"/video/720p/seg-{seg}.ts", name="VIDEO:hls_seg")
    @task(4)  # 其他：瀏覽/搜尋
    def browse(self):
        self.client.get("/", name="WEB:index")



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