
## 1. SocialUser 的請求行為

- `wait_time = constant_throughput(1)` 表示每個 SocialUser 實例**每秒執行 1 個 task**
- `target_server_count: 30` 表示每個 SocialUser 會從 30 個目標伺服器中**隨機選擇一個**發送請求
- **關鍵點**：`_get_target_host()` 使用 `random.choice(self.target_servers)`，所以每次請求都是隨機選擇 30 個中的 1 個，而不是輪流向所有 30 個發送

**實際行為**：
- 每個 SocialUser 實例每秒執行 1 個 task（browse 或 feed_scroll）
- 每個 task 會隨機選擇 30 個目標伺服器中的 1 個發送請求
- 如果有多個 SocialUser 實例同時運行，整體的請求分布會趨向平均分散到 30 個伺服器

## 2. browse 和 feed_scroll 的特性差異

### `browse` (@task(4) - 權重 4)
```python
@task(4)
def browse(self):
    target_host = self._get_target_host()
    url = f"http://{target_host}/"
    self.client.get(url, name="WEB:index")
```
- **功能**：瀏覽首頁
- **請求類型**：單純的 GET 請求到根路徑 `/`
- **特性**：
  - 輕量級，只發送 1 個 HTTP GET 請求
  - 模擬用戶瀏覽網站首頁的行為
  - 權重 4（在 10 次 task 中約執行 4 次）

### `feed_scroll` (@task(6) - 權重 6)
```python
@task(6)
def feed_scroll(self):
    target_host = self._get_target_host()
    url = f"http://{target_host}/feed?since={random.randint(1, 1_000_000_000)}"
    self.client.get(url, name="SOCIAL:feed")
    # 30% 機率會額外發送互動請求
    if random.random()<0.3:
        url = f"http://{target_host}/react"
        self.client.post(url, json={"pid":random.randint(1, 1_000_000)}, name="SOCIAL:react")
```
- **功能**：瀏覽社群動態流
- **請求類型**：GET + 可能的 POST
- **特性**：
  - **較重量級**：至少 1 個 GET 請求，30% 機率會再發送 1 個 POST 請求
  - 模擬用戶滑動社群動態並可能互動（按讚/評論）
  - 權重 6（在 10 次 task 中約執行 6 次）
  - 帶有隨機參數 `since`，模擬分頁或時間戳查詢
  - POST 請求包含 JSON 資料，模擬真實的社群互動

**綜合比較**：
- `feed_scroll` 發生頻率更高（60% vs 40%）
- `feed_scroll` 可能產生 2 個請求（GET + POST），`browse` 只有 1 個
- `feed_scroll` 更能模擬真實社群平台的高互動性負載