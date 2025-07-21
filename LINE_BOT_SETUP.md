# Line Bot 設定說明

## 功能說明
當有人完成報名、取消報名、修改報名資料或管理員切換繳費狀態時，系統會自動將最新的報名名單發送到指定的 Line 群組。

## 設定步驟

### 1. 創建 Line Bot
1. 前往 [Line Developers Console](https://developers.line.biz/)
2. 登入您的 Line 帳號
3. 創建一個新的 Provider（如果還沒有的話）
4. 在 Provider 下創建一個新的 Channel
5. 選擇 "Messaging API" 類型
6. 填寫 Channel 資訊並創建

### 2. 獲取 Line Bot 憑證
在 Line Developers Console 中：
1. 進入您創建的 Channel
2. 在 "Messaging API" 標籤頁中：
   - 複製 "Channel access token"
   - 複製 "Channel secret"

### 3. 將 Bot 加入群組
1. 掃描 Channel 的 QR Code 或使用 Channel ID 將 Bot 加入您的 Line 群組
2. 在群組中發送任意訊息
3. 前往 Line Developers Console 的 "Messaging API" 標籤頁
4. 在 "Webhook URL" 欄位中設定：`https://your-domain.com/line/webhook`
5. 啟用 "Use webhook"

### 4. 獲取群組 ID
1. 在群組中發送訊息
2. 前往 Line Developers Console 的 "Messaging API" 標籤頁
3. 在 "Webhook URL" 下方會顯示群組 ID

### 5. 設定環境變數
在您的部署環境中設定以下環境變數：

```
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
LINE_CHANNEL_SECRET=your-channel-secret
LINE_GROUP_ID=your-group-id
```

### 6. 部署更新
1. 更新 requirements.txt（已包含 line-bot-sdk）
2. 重新部署應用程式
3. 確保環境變數已正確設定

## 訊息格式
發送到 Line 群組的訊息包含：
- 活動基本資訊（標題、日期、地點、費用）
- 報名統計（報名人數、總參與人數、已繳費人數、已收費用）
- 詳細報名名單（姓名、電話、參與人數、繳費狀態）

## 注意事項
- 確保 Line Bot 有權限發送訊息到群組
- 如果環境變數未設定，系統會跳過發送 Line 訊息但不會影響其他功能
- 所有錯誤都會記錄在應用程式日誌中 