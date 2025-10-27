from locust import FastHttpUser, User, task, constant_pacing, constant_throughput, constant, events
from locust.contrib.mqtt import MqttUser, MqttClient
import random, os
import paho.mqtt.client as mqtt, os, time, random, json
import dns.message
import dns.rdatatype
import dns.query
import socket

class SocialUser(FastHttpUser):
    """社群互動用戶：快速、頻繁的請求"""
    wait_time = constant_throughput(1)  # 每秒 1 次 task（適合短時間 task）

    # Configuration: 可透過環境變數覆寫
    # 例如：TARGET_CIDR=10.60.201.0/16 TARGET_SCHEME=http TARGET_PORT=80
    target_cidr = os.environ.get("TARGET_CIDR", "10.60.201.0/16")
    target_scheme = os.environ.get("TARGET_SCHEME", "http")
    # 如果要使用非標準 port，例如 8080，設定 TARGET_PORT
    target_port = os.environ.get("TARGET_PORT")

    # 準備 ipaddress 網路物件（延遲 import 以避免啟動時錯誤）
    import ipaddress
    try:
        _network = ipaddress.ip_network(target_cidr)
    except Exception:
        _network = ipaddress.ip_network("10.60.201.0/16")

    def _random_ip_in_network(self):
        """Return a random host IP (as string) from the configured CIDR/network.

        Excludes network and broadcast addresses for IPv4 when possible.
        """
        # For very large networks, avoid building full list; sample using int arithmetic
        net = self._network
        # Get first and last usable IP integers
        first = int(net.network_address)
        last = int(net.broadcast_address)
        # Exclude network and broadcast for IPv4 / >=4 addresses
        if last - first > 2:
            first += 1
            last -= 1

        rand_int = random.randint(first, last)
        return str(self.ipaddress.ip_address(rand_int))
    
    @task(6)  # 權重：社群
    def feed_scroll(self):
        # 圖片/短片混合
        # 選一個隨機目標 IP，並使用絕對 URL 發送請求
        target_ip = self._random_ip_in_network()
        port_part = f":{self.target_port}" if self.target_port else ""
        base = f"{self.target_scheme}://{target_ip}{port_part}"

        self.client.get(f"{base}/feed?since={random.randint(1, 1_000_000_000)}", name="SOCIAL:feed")
        # 小上傳（評論/按讚）
        if random.random()<0.3:
            self.client.post("/react", json={"pid":random.randint(1, 1_000_000)}, name="SOCIAL:react")
    
    @task(4)  # 其他：瀏覽/搜尋
    def browse(self):
        target_ip = self._random_ip_in_network()
        port_part = f":{self.target_port}" if self.target_port else ""
        base = f"{self.target_scheme}://{target_ip}{port_part}"
        self.client.get(f"{base}/", name="WEB:index")


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


class DnsLoad(User):
    """DNS 查詢用戶：隨機發送各種 DNS 查詢"""
    
    # DNS 伺服器設定（可以在 config-users.json 中覆寫）
    dns_server = "1.1.1.1"  # 預設使用 Cloudflare DNS
    dns_port = 53
    
    # 等待時間
    wait_time = constant_throughput(1)  # 每秒 1 個查詢
    
    # 隨機域名列表（可以根據需求調整）
    domains = [
        "google.com",
        "example.com",
        "github.com",
        "stackoverflow.com",
        "youtube.com",
        "facebook.com",
        "twitter.com",
        "amazon.com",
        "wikipedia.org",
        "reddit.com",
        "linkedin.com",
        "netflix.com",
        "instagram.com",
        "apple.com",
        "microsoft.com",
    ]
    
    # DNS 查詢類型（可以隨機選擇不同的查詢類型）
    query_types = [
        (dns.rdatatype.A, "A"),      # IPv4 地址
        (dns.rdatatype.AAAA, "AAAA"), # IPv6 地址
        (dns.rdatatype.MX, "MX"),     # 郵件交換記錄
        (dns.rdatatype.TXT, "TXT"),   # 文本記錄
        (dns.rdatatype.NS, "NS"),     # 名稱伺服器
        (dns.rdatatype.CNAME, "CNAME"), # 別名記錄
    ]
    
    def _send_dns_query(self, query_name: str, query_type, query_type_name: str):
        """發送 DNS 查詢並記錄統計"""
        start_time = time.time()
        response_length = 0
        exception = None
        
        try:
            # 建立 DNS 查詢
            q = dns.message.make_query(query_name, query_type)
            
            # 發送 UDP 查詢
            response = dns.query.udp(q, self.dns_server, timeout=5, port=self.dns_port)
            
            # 計算響應長度
            response_length = len(response.to_wire())
            
            # 計算響應時間（毫秒）
            response_time = (time.time() - start_time) * 1000
            
            # 檢查響應碼
            if response.rcode() != dns.rcode.NOERROR:
                exception = Exception(f"DNS query failed with rcode: {dns.rcode.to_text(response.rcode())}")
            
        except dns.exception.Timeout as e:
            response_time = (time.time() - start_time) * 1000
            exception = e
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            exception = e
        
        # 觸發 Locust 事件以記錄統計
        self.environment.events.request.fire(
            request_type="DNS",
            name=f"DNS:{query_type_name}:{query_name}",
            response_time=response_time,
            response_length=response_length,
            exception=exception,
            context={}
        )
    
    @task(10)
    def random_a_query(self):
        """隨機 A 記錄查詢（最常見的查詢類型）"""
        domain = random.choice(self.domains)
        self._send_dns_query(domain, dns.rdatatype.A, "A")
    
    @task(5)
    def random_aaaa_query(self):
        """隨機 AAAA 記錄查詢（IPv6 地址）"""
        domain = random.choice(self.domains)
        self._send_dns_query(domain, dns.rdatatype.AAAA, "AAAA")
    
    @task(3)
    def random_mixed_query(self):
        """隨機混合類型的查詢"""
        domain = random.choice(self.domains)
        qtype, qtype_name = random.choice(self.query_types)
        self._send_dns_query(domain, qtype, qtype_name)
    
    @task(2)
    def custom_domain_query(self):
        """對自定義域名進行查詢（可以用來測試特定的 DNS 伺服器）"""
        # 可以在這裡添加更多的自定義域名或子域名
        subdomain = random.choice(["www", "mail", "ftp", "api", "cdn", "blog"])
        domain = random.choice(self.domains)
        full_domain = f"{subdomain}.{domain}"
        self._send_dns_query(full_domain, dns.rdatatype.A, "A")

