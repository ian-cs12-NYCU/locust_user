from locust import HttpUser, User, task, between
from requests_toolbelt.adapters.source import SourceAddressAdapter
import random, os, time, json, logging
import dns.message
import dns.rdatatype
import dns.query
import urllib3
from pathlib import Path
from utils.ip_manager import get_source_ip  # 從 utils 模組導入
from utils.target_server import get_target_servers  # 導入目標伺服器管理器

# ==========================================
# SSL 設定：忽略自簽憑證的安全性警告
# ==========================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定日誌格式，方便除錯
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# LRD 參數設定 (Long Range Dependence)
# ==========================================
# Alpha 越接近 1.0，長依賴(LRD)越強，突發越明顯
# 建議範圍 1.2 (強) ~ 1.6 (中)
PARETO_ALPHA_SESSION = 1.4  # 用於決定看多久 (ON Period)
PARETO_ALPHA_WAIT = 1.4     # 用於決定休息多久 (OFF Period)

def _load_user_config():
    """載入 config-users.json 配置檔案"""
    base_dir = Path(__file__).parent
    config_file = base_dir / 'profiles' / 'config-users.json'
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Config] Error loading config-users.json: {e}")
        return []

def _get_target_count_for_user(user_class_name: str) -> int:
    """從配置中獲取特定 User 類型的 target_server_count"""
    config = _load_user_config()
    for user_config in config:
        if user_config.get('user_class_name') == user_class_name:
            return user_config.get('target_server_count', 0)
    return 0

def _get_protocol_for_user(user_class_name: str) -> str:
    """從配置中獲取特定 User 類型的 protocol。預設為 https"""
    config = _load_user_config()
    for user_config in config:
        if user_config.get('user_class_name') == user_class_name:
            protocol = user_config.get('protocol', 'https')
            # 正規化為小寫
            return protocol.lower() if protocol else 'https'
    # 預設使用 https
    return 'https'

class SocialUser(HttpUser):
    """社群互動用戶：使用 requests.Session 綁定來源 IP"""
    wait_time = between(30, 100)  # 在 30 到 100 秒之間隨機等待
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 每個 User 實例在創建時，傳入自己的類名來獲取 IP
        self.source_ip = get_source_ip(self.__class__.__name__)
        
        # 獲取协议配置
        self.protocol = _get_protocol_for_user(self.__class__.__name__)
        
        # 獲取目標伺服器列表
        target_count = _get_target_count_for_user(self.__class__.__name__)
        self.target_servers = get_target_servers(self.__class__.__name__, target_count)
        print(f"[SocialUser] Initialized with source IP: {self.source_ip}, "
              f"protocol: {self.protocol}, target servers: {self.target_servers}")
    
    def on_start(self):
        """在 on_start 中掛載 SourceAddressAdapter"""
        print(f"[SocialUser] 🔧 Mounting SourceAddressAdapter for IP: {self.source_ip}")
        adapter = SourceAddressAdapter((self.source_ip, 0))
        self.client.mount("http://", adapter)
        self.client.mount("https://", adapter)
        print(f"[SocialUser] ✅ Adapter mounted. All requests from this user will use {self.source_ip}")
    
    def _get_target_host(self):
        """從目標伺服器列表中隨機選擇一個，返回不含 http:// 前綴的主機地址"""
        if self.target_servers:
            return random.choice(self.target_servers)
        # 如果沒有配置目標伺服器，使用預設 host（移除可能存在的 http:// 前綴）
        host = self.host
        if host.startswith('http://'):
            host = host[7:]
        elif host.startswith('https://'):
            host = host[8:]
        return host
    
    @task(6)  # 權重：社群
    def feed_scroll(self):
        # 圖片/短片混合
        target_host = self._get_target_host()
        url = f"{self.protocol}://{target_host}/feed?since={random.randint(1, 1_000_000_000)}"
        logger.debug(f"[SocialUser] Requesting: {url}")
        self.client.get(url, name="SOCIAL:feed", verify=False)
        # 小上傳（評論/按讚）
        if random.random()<0.3:
            url = f"{self.protocol}://{target_host}/react"
            logger.debug(f"[SocialUser] Posting to: {url}")
            self.client.post(url, json={"pid":random.randint(1, 1_000_000)}, name="SOCIAL:react", verify=False)
    
    @task(4)  # 其他：瀏覽/搜尋
    def browse(self):
        target_host = self._get_target_host()
        url = f"{self.protocol}://{target_host}/"
        logger.debug(f"[SocialUser] Browsing: {url}")
        self.client.get(url, name="WEB:index", verify=False)


class VideoUser(HttpUser):
    """影音串流用戶：模擬 LRD 特性的長時間連續 session"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 傳入自己的類名來獲取 IP
        self.source_ip = get_source_ip(self.__class__.__name__)
        
        # 獲取协议配置
        self.protocol = _get_protocol_for_user(self.__class__.__name__)
        
        # 獲取目標伺服器列表
        target_count = _get_target_count_for_user(self.__class__.__name__)
        self.target_servers = get_target_servers(self.__class__.__name__, target_count)
        print(f"[VideoUser] Initialized with source IP: {self.source_ip}, "
              f"protocol: {self.protocol}, target servers: {self.target_servers}")

    def on_start(self):
        """在 on_start 中掛載 SourceAddressAdapter"""
        print(f"[VideoUser] 🔧 Mounting SourceAddressAdapter for IP: {self.source_ip}")
        adapter = SourceAddressAdapter((self.source_ip, 0))
        self.client.mount("http://", adapter)
        self.client.mount("https://", adapter)
        print(f"[VideoUser] ✅ Adapter mounted. All requests from this user will use {self.source_ip}")
    
    def _get_target_host(self):
        """從目標伺服器列表中隨機選擇一個，返回不含 http:// 前綴的主機地址"""
        if self.target_servers:
            return random.choice(self.target_servers)
        # 如果沒有配置目標伺服器，使用預設 host（移除可能存在的 http:// 前綴）
        host = self.host
        if host.startswith('http://'):
            host = host[7:]
        elif host.startswith('https://'):
            host = host[8:]
        return host
    
    def _parse_playlist(self, playlist_content: str) -> list:
        """
        Parse M3U8 playlist and return a list of segment filenames.

        Args:
            playlist_content: playlist text content

        Returns:
            list of segment filenames (basename only)
        """
        segments = []
        for line in playlist_content.split('\n'):
            line = line.strip()
            # 跳過註解和空行
            if line and not line.startswith('#'):
                # 處理相對路徑（例如：../../seg-734.ts）
                if line.startswith('../'):
                    # 移除 ../ 前綴，只保留檔名
                    filename = line.split('/')[-1]
                    segments.append(filename)
                else:
                    segments.append(line)
        return segments
    
    # =================================================================
    # [LRD 修改點 1] OFF Period (Inter-session time) - Pareto 分布
    # =================================================================
    def pareto_wait_time(self):
        """
        模擬看完一部影片後的休息時間。
        使用 Pareto 分佈：多數時間很短（連續看），偶爾非常長（離開）。
        """
        # 基礎休息時間 (Scale)
        scale = 5.0 
        # 生成 Pareto 隨機數
        wait = random.paretovariate(PARETO_ALPHA_WAIT) * scale
        # 為了避免線程睡死 (例如睡 10 小時)，設定一個合理的上限 (例如 5 分鐘)
        max_wait = 300.0
        actual_wait = min(wait, max_wait)
        logger.debug(f"[VideoUser] ⏰ Pareto Wait Time: {actual_wait:.2f}s (raw: {wait:.2f}s)")
        return actual_wait

    # 將這個方法指派給 Locust 的 wait_time
    wait_time = pareto_wait_time
    
    @task
    def video_watch_session(self):
        target_host = self._get_target_host()
        
        # 1. 抓 playlist（模擬播放器初始化）
        # DN 伺服器只有 video-1 到 video-100（共 101 個）
        video_id = random.randint(1, 100)
        playlist_url = f"{self.protocol}://{target_host}/video/720p/video-{video_id}/playlist.m3u8"
        
        logger.info(f"[VideoUser] 🎬 Starting video session - Playlist URL: {playlist_url}")
        
        try:
            with self.client.get(playlist_url, name="VIDEO:playlist", catch_response=True, verify=False) as resp:
                if resp.status_code != 200:
                    logger.error(f"[VideoUser] ❌ Playlist request failed: {playlist_url} - "
                               f"Status: {resp.status_code}, Response: {resp.text[:200]}")
                    resp.failure(f"Playlist failed with status {resp.status_code}")
                    return  # 如果 playlist 失敗，直接結束 session
                
                # 解析 playlist 獲取實際的 segment 列表
                segments = self._parse_playlist(resp.text)
                logger.info(f"[VideoUser] 📝 Parsed {len(segments)} segments from playlist")
                
                if not segments:
                    logger.warning(f"[VideoUser] ⚠️ No segments found in playlist: {playlist_url}")
                    resp.failure("No segments found in playlist")
                    return
        
        except Exception as e:
            logger.exception(f"[VideoUser] ❌ Exception while fetching playlist {playlist_url}: {e}")
            return
        
        # =================================================================
        # [LRD 修改點 2] ON Period (Session Length) - Pareto 分布
        # =================================================================
        # 使用 Pareto 分佈決定要看幾個片段
        # Scale = 10，代表最少傾向於看 10 段左右，但有機會看非常多
        pareto_val = random.paretovariate(PARETO_ALPHA_SESSION)
        num_segments_to_watch = int(pareto_val * 10)
        
        # 限制範圍：至少看 1 段，最多把整部片看完 (或設定上限如 200)
        watch_segments = min(max(1, num_segments_to_watch), len(segments), 200)
        
        logger.info(f"[VideoUser] 📺 Pareto Decision: Will watch {watch_segments} segments "
                   f"(Pareto value: {pareto_val:.2f}, Total available: {len(segments)})")
        
        # 3. 從 playlist 中隨機選擇起始位置
        if len(segments) > watch_segments:
            start_idx = random.randint(0, len(segments) - watch_segments)
        else:
            start_idx = 0
        
        # 4. 連續抓取 segments
        for i in range(watch_segments):
            seg_idx = (start_idx + i) % len(segments)
            seg_filename = segments[seg_idx]
            
            # 構建完整的 segment URL（根據 playlist 中的相對路徑）
            seg_url = f"{self.protocol}://{target_host}/video/720p/{seg_filename}"
            
            logger.debug(f"[VideoUser] 📦 Fetching segment [{i+1}/{watch_segments}]: {seg_url}")
            
            try:
                with self.client.get(seg_url, name="VIDEO:hls_seg", catch_response=True, timeout=30, verify=False) as resp:
                    if resp.status_code != 200:
                        logger.error(f"[VideoUser] ❌ Segment request failed: {seg_url} - "
                                   f"Status: {resp.status_code}")
                        resp.failure(f"Segment {seg_filename} failed with status {resp.status_code}")
                        
                        # 遇到 5xx 錯誤就中斷 session（模擬播放器停止）
                        if resp.status_code >= 500:
                            logger.warning(f"[VideoUser] 🛑 Stopping session due to server error")
                            break
                    else:
                        logger.debug(f"[VideoUser] ✅ Segment {seg_filename} downloaded successfully "
                                   f"({len(resp.content)} bytes)")
            
            except Exception as e:
                logger.exception(f"[VideoUser] ❌ Exception while fetching segment {seg_url}: {e}")
                # 可選：遇到異常也中斷 session
                break
            
            # =================================================================
            # [LRD 修改點 3] Bitrate 控制 (Micro-level)
            # =================================================================
            # 目標：平均 Bitrate 3~7 Mbps
            # 平均檔案大小 16Mb (2MB) / 平均間隔 3.2s = 5 Mbps
            # 設定範圍：2.3s ~ 5.3s
            sleep_time = random.uniform(2.3, 5.3)
            logger.debug(f"[VideoUser] ⏸️ Sleeping {sleep_time:.2f}s before next segment")
            time.sleep(sleep_time)
            
            # 可選：模擬極小機率的隨機中斷（模擬斷網，1% 機率）
            # 移除舊的 5% 跳出率，因為已經用 Pareto 決定了 session 長度
            if random.random() < 0.01:
                logger.info(f"[VideoUser] 🔌 Network interruption - stopping after {i+1} segments")
                break
        
        logger.info(f"[VideoUser] ✅ Video session completed")


class DnsLoad(User):
    """DNS 查詢用戶：隨機發送各種 DNS 查詢"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 傳入自己的類名來獲取 IP
        self.source_ip = get_source_ip(self.__class__.__name__)
        
        # 獲取目標伺服器列表（DNS 伺服器）
        target_count = _get_target_count_for_user(self.__class__.__name__)
        self.target_servers = get_target_servers(self.__class__.__name__, target_count)
        print(f"[DnsLoad] Initialized with source IP: {self.source_ip}, "
              f"target DNS servers: {self.target_servers}")

        # If the user config contains an explicit dns_server for DnsLoad, prefer that
        try:
            cfg = _load_user_config()
            for item in cfg:
                if item.get('user_class_name') == self.__class__.__name__:
                    # override defaults if present
                    if item.get('dns_server'):
                        self.dns_server = item.get('dns_server')
                    if item.get('dns_port'):
                        self.dns_port = item.get('dns_port')
                    break
        except Exception:
            # keep defaults if config can't be read
            pass

    # DNS 伺服器設定（可以在 config-users.json 中覆寫）
    dns_server = "1.1.1.1"  # 預設使用 Cloudflare DNS
    dns_port = 53
    
    def _get_target_dns_server(self):
        """從目標伺服器列表中隨機選擇一個 DNS 伺服器"""
        # Prefer an explicit configured DNS server (from config-users.json or default attribute).
        if getattr(self, 'dns_server', None):
            return self.dns_server

        # Fallback: if a pool of target_servers was explicitly provided and intended to be DNS servers,
        # choose one at random. Otherwise fall back to the dns_server attribute.
        if self.target_servers:
            return random.choice(self.target_servers)

        return self.dns_server
    
    # 等待時間
    wait_time = between(1, 3)  # 每秒 1 個查詢
    
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
    # Restrict queries to A records only for this environment — user requested A-only testing
    query_types = [
        (dns.rdatatype.A, "A"),      # IPv4 address only
    ]
    
    def _send_dns_query(self, query_name: str, query_type, query_type_name: str):
        """發送 DNS 查詢並記錄統計"""
        # 動態選擇目標 DNS 伺服器
        target_dns = self._get_target_dns_server()
        
        start_time = time.time()
        response_length = 0
        exception = None
        
        try:
            # 建立 DNS 查詢
            q = dns.message.make_query(query_name, query_type)
            
            # 發送 UDP 查詢，並綁定來源 IP，使用動態選擇的目標 DNS 伺服器
            response = dns.query.udp(q, target_dns, timeout=5, port=self.dns_port, source=self.source_ip)
            
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
            name=f"DNS:{query_type_name}:{query_name}@{target_dns}",
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
    
    
    @task(2)
    def custom_domain_query(self):
        """對自定義域名進行查詢（可以用來測試特定的 DNS 伺服器）"""
        # 可以在這裡添加更多的自定義域名或子域名
        subdomain = random.choice(["www", "mail", "ftp", "api", "cdn", "blog"])
        domain = random.choice(self.domains)
        full_domain = f"{subdomain}.{domain}"
        # Ensure only A queries are sent
        self._send_dns_query(full_domain, dns.rdatatype.A, "A")
