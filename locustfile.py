from locust import HttpUser, User, task, constant_pacing, constant_throughput, constant, events
from requests_toolbelt.adapters.source import SourceAddressAdapter
import random, os
import dns.message
import dns.rdatatype
import dns.query

class SocialUser(HttpUser):
    """社群互動用戶：使用 requests.Session 綁定來源 IP"""
    wait_time = constant_throughput(1)  # 每秒 1 次 task（適合短時間 task）
    
    # 設置 source IP
    source_ip = os.getenv("UE_IP", "10.60.100.1")
    
    def on_start(self):
        """在 on_start 中掛載 SourceAddressAdapter"""
        print(f"[SocialUser] � Mounting SourceAddressAdapter for IP: {self.source_ip}")
        adapter = SourceAddressAdapter((self.source_ip, 0))
        self.client.mount("http://", adapter)
        self.client.mount("https://", adapter)
        print(f"[SocialUser] ✅ Adapter mounted. All requests from this user will use {self.source_ip}")
    
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


class VideoUser(HttpUser):
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
