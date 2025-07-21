# Line 活動報名系統

這是一個基於 Flask 的活動報名系統，可以讓使用者透過 Line 分享連結進行活動報名，並具備自動回傳報名名單到 Line 群組的功能。

## 功能特點

- 活動報名頁面
- 即時查看報名者名單
- 後台管理系統
  - 活動管理（新增、編輯、刪除）
  - 自訂報名欄位
  - 報名統計
- Line 分享功能
- **Line Bot 自動回傳報名名單** ⭐ 新功能
  - 當有人完成報名時，自動發送報名名單到 Line 群組
  - 當有人取消報名時，自動更新 Line 群組的報名名單
  - 當有人修改報名資料時，自動更新 Line 群組的報名名單
  - 當管理員切換繳費狀態時，自動更新 Line 群組的報名名單

## 安裝說明

1. 安裝所需套件：
```bash
pip install -r requirements.txt
```

2. 執行應用程式：
```bash
python app.py
```

## 系統需求

- Python 3.8+
- MongoDB 4.0+
- 現代瀏覽器（Chrome、Firefox、Safari、Edge）
- Line Developers Console 帳號（用於 Line Bot 功能）

## 技術架構

### 後端技術
- **Flask 3.0.0** - Python Web 框架
- **Flask-Login 0.6.3** - 用戶認證管理
- **PyMongo 4.6.1** - MongoDB 資料庫連接
- **Gunicorn 21.2.0** - WSGI 伺服器
- **Python-dotenv 1.0.0** - 環境變數管理

### Line Bot 整合
- **Line Bot SDK 3.5.0** - 官方 Line Bot API 套件
- **Line Messaging API** - 用於發送訊息到群組
- **Line Webhook** - 接收 Line 平台事件

### 前端技術
- **Bootstrap 5** - 響應式 UI 框架
- **Font Awesome** - 圖示庫
- **JavaScript** - 前端互動功能

### 雲端部署
- **Render** - 雲端平台部署
- **MongoDB Atlas** - 雲端資料庫

## 預設帳號

系統預設提供兩種管理者帳號：

1. 總管理者
- 帳號：kt
- 密碼：kingmax00
- 權限：完整系統控制

2. 一般管理者
- 帳號：admin
- 密碼：admin123
- 權限：基本管理功能

## 版本歷程

- **v3.1**：新增 Line Bot 自動回傳報名名單功能 ⭐
  - 整合 Line Bot SDK 3.5.0
  - 自動發送報名更新到 Line 群組
  - 支援報名、取消、修改、繳費狀態變更通知
  - 新增 Line Bot 診斷工具
- v3.0：完整版本發布，包含所有核心功能
- v2.6：改進使用者權限和介面顯示
- v2.5：新增活動隱藏功能和 KT 管理者帳號
- v2.3：修復報名系統顯示問題
- v2.1：新增報名資料修改功能
- v2.0：加入管理後台功能
- v1.0：基礎版本發布

## Line Bot 設定

### 環境變數設定
在部署環境中需要設定以下環境變數：
```
LINE_CHANNEL_ACCESS_TOKEN=您的Channel Access Token
LINE_CHANNEL_SECRET=您的Channel Secret
LINE_GROUP_ID=您的Line群組ID
```

### Line Bot 權限設定
在 Line Developers Console 中需要啟用：
- **Allow bot to join group chats** - 允許 Bot 加入群組聊天
- **Use webhook** - 啟用 Webhook 功能

詳細設定說明請參考 `LINE_BOT_SETUP.md` 和 `DEPLOYMENT_GUIDE.md`。

## 注意事項

1. 首次使用請務必修改預設管理者密碼
2. 定期備份資料庫
3. 建議定期更新系統以獲得最新功能和安全性更新
4. Line Bot 功能需要正確設定環境變數和權限

## 聯絡資訊

如有任何問題或建議，請聯絡系統管理者：
- Email: kt.liang@merry.com.tw
- Line: @ktliang

## 授權資訊

本系統為清華 EMBA24 專用，著作權所有 © 2024 KT. Liang
