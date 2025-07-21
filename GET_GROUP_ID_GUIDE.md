# 🎯 獲取 LINE_GROUP_ID 的簡單方法

## 方法 1：透過應用程式日誌（推薦）

### 步驟 1：部署程式碼
1. 推送程式碼到 GitHub：
   ```bash
   git add .
   git commit -m "Add Line webhook logging for group ID detection"
   git push origin main
   ```

### 步驟 2：設定環境變數
在 Render 中設定：
- `LINE_CHANNEL_ACCESS_TOKEN` = 您的 Channel Access Token
- `LINE_CHANNEL_SECRET` = 您的 Channel Secret

### 步驟 3：將 Bot 加入群組
1. 掃描 Line Developers Console 中的 QR Code
2. 將 Bot 加入您的 Line 群組

### 步驟 4：發送測試訊息
1. 在群組中發送任意訊息（例如：「測試」）
2. 等待 1-2 分鐘

### 步驟 5：查看應用程式日誌
1. 登入 [Render Dashboard](https://dashboard.render.com/)
2. 找到您的 `event-registration` 服務
3. 點擊 "Logs" 標籤
4. 尋找類似這樣的日誌：
   ```
   收到 Line webhook: {"events":[{"type":"message","source":{"type":"group","groupId":"C1234567890abcdef1234567890abcdef"},"message":{"type":"text","text":"測試"}}]}
   ```

### 步驟 6：複製群組 ID
從日誌中複製 `groupId` 的值：
```
C1234567890abcdef1234567890abcdef
```

### 步驟 7：設定群組 ID
在 Render 環境變數中添加：
```
LINE_GROUP_ID=C1234567890abcdef1234567890abcdef
```

## 方法 2：使用測試端點

### 步驟 1：測試連接
訪問：`https://event-registration-la1k.onrender.com/line/test`

如果顯示 "Line Bot 連接正常"，表示設定正確。

### 步驟 2：發送訊息並查看日誌
按照方法 1 的步驟 3-6 操作。

## 方法 3：手動檢查 Line Developers Console

### 步驟 1：啟用 Webhook
1. 在 Line Developers Console 中設定 Webhook URL：
   ```
   https://event-registration-la1k.onrender.com/line/webhook
   ```
2. 啟用 "Use webhook"

### 步驟 2：發送測試訊息
1. 在群組中發送訊息
2. 點擊 "Verify" 按鈕
3. 查看是否有事件記錄出現

## 常見問題

### Q: 沒有看到群組 ID？
A: 確保：
- Bot 已加入群組
- 在群組中發送了訊息
- Webhook URL 已正確設定
- 等待 1-2 分鐘讓事件傳播

### Q: 應用程式日誌中沒有 webhook 記錄？
A: 檢查：
- LINE_CHANNEL_ACCESS_TOKEN 是否正確
- LINE_CHANNEL_SECRET 是否正確
- Webhook URL 是否正確設定

### Q: 群組 ID 格式是什麼？
A: 群組 ID 通常以 `C` 開頭，例如：
```
C1234567890abcdef1234567890abcdef
```

## 完成設定後
設定好所有環境變數後，重新部署應用程式，然後測試報名功能。當有人報名時，Line 群組應該會收到自動更新的報名名單！ 