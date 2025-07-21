# 雲端部署指南 - Line Bot 功能

## 功能說明
✅ 已完成的功能：
- 當有人完成報名時，自動將報名名單發送到 Line 群組
- 當有人取消報名時，自動更新 Line 群組的報名名單
- 當有人修改報名資料時，自動更新 Line 群組的報名名單
- 當管理員切換繳費狀態時，自動更新 Line 群組的報名名單

## 部署步驟

### 1. 更新 GitHub 倉庫
1. 將修改後的檔案推送到 GitHub：
   ```bash
   git add .
   git commit -m "Add Line Bot integration for registration updates"
   git push origin main
   ```

### 2. 設定 Line Bot
1. 前往 [Line Developers Console](https://developers.line.biz/)
2. 登入您的 Line 帳號
3. 創建一個新的 Provider（如果還沒有的話）
4. 在 Provider 下創建一個新的 Channel
5. 選擇 "Messaging API" 類型
6. 填寫 Channel 資訊並創建

### 3. 獲取 Line Bot 憑證
在 Line Developers Console 中：
1. 進入您創建的 Channel
2. 在 "Messaging API" 標籤頁中：
   - 複製 "Channel access token"
   - 複製 "Channel secret"

### 4. 將 Bot 加入群組
1. 掃描 Channel 的 QR Code 或使用 Channel ID 將 Bot 加入您的 Line 群組
2. 在群組中發送任意訊息
3. 前往 Line Developers Console 的 "Messaging API" 標籤頁
4. 在 "Webhook URL" 欄位中設定：`https://event-registration-la1k.onrender.com/line/webhook`
5. 啟用 "Use webhook"

### 5. 獲取群組 ID
1. 在群組中發送訊息
2. 前往 Line Developers Console 的 "Messaging API" 標籤頁
3. 在 "Webhook URL" 下方會顯示群組 ID

### 6. 在 Render 上設定環境變數
1. 登入 [Render Dashboard](https://dashboard.render.com/)
2. 找到您的 `event-registration` 服務
3. 點擊 "Environment" 標籤
4. 添加以下環境變數：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
   LINE_CHANNEL_SECRET=your-channel-secret
   LINE_GROUP_ID=your-group-id
   ```

### 7. 重新部署
1. 在 Render Dashboard 中點擊 "Manual Deploy"
2. 選擇 "Deploy latest commit"
3. 等待部署完成

## 測試功能
1. 前往您的活動報名系統：https://event-registration-la1k.onrender.com
2. 選擇一個活動進行報名
3. 檢查 Line 群組是否收到報名更新訊息
4. 測試其他功能（取消報名、修改報名、切換繳費狀態）

## 訊息格式範例
發送到 Line 群組的訊息會包含：
```
📋 第6組班聚活動踩點
📅 活動日期：2025-08-02 至 2025-09-20
📍 地點：苗栗（暫定）
💰 費用：NT$ 0

📊 報名統計：
• 報名人數：2 人
• 總參與人數：2 人
• 已繳費：1 人
• 已收費用：NT$ 0

📝 報名名單：
1. KT (0989196925) ✅已繳費
2. 小明 (0912345678)
```

## 故障排除
- 如果沒有收到 Line 訊息，檢查：
  1. 環境變數是否正確設定
  2. Line Bot 是否已加入群組
  3. Webhook URL 是否正確設定
  4. 查看 Render 的應用程式日誌

## 注意事項
- 確保 Line Bot 有權限發送訊息到群組
- 如果環境變數未設定，系統會跳過發送 Line 訊息但不會影響其他功能
- 所有錯誤都會記錄在 Render 的應用程式日誌中 