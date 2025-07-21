#!/usr/bin/env python3
"""
Line 群組 ID 獲取工具
使用方法：
1. 設定環境變數 LINE_CHANNEL_ACCESS_TOKEN
2. 將 Line Bot 加入群組
3. 在群組中發送訊息
4. 運行此腳本
"""

import os
import requests
from datetime import datetime, timedelta

def get_line_group_id():
    """獲取 Line 群組 ID"""
    
    # 獲取 Channel Access Token
    access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not access_token:
        print("❌ 請先設定環境變數 LINE_CHANNEL_ACCESS_TOKEN")
        print("在 Line Developers Console 中複製 Channel Access Token")
        return None
    
    # Line API 端點
    url = "https://api.line.me/v2/bot/message/list"
    
    # 設定請求標頭
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        # 獲取最近的訊息
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ 成功連接到 Line API")
            print(f"📊 找到 {len(data.get('messages', []))} 條訊息")
            
            # 尋找群組訊息
            for message in data.get('messages', []):
                if message.get('source', {}).get('type') == 'group':
                    group_id = message['source']['groupId']
                    print(f"🎯 找到群組 ID: {group_id}")
                    return group_id
            
            print("❌ 沒有找到群組訊息")
            print("請確保：")
            print("1. Line Bot 已加入群組")
            print("2. 在群組中發送了訊息")
            print("3. 等待幾分鐘後再試")
            
        else:
            print(f"❌ API 請求失敗: {response.status_code}")
            print(f"錯誤訊息: {response.text}")
            
    except Exception as e:
        print(f"❌ 發生錯誤: {str(e)}")
    
    return None

def test_line_connection():
    """測試 Line Bot 連接"""
    
    access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not access_token:
        print("❌ 請先設定 LINE_CHANNEL_ACCESS_TOKEN")
        return False
    
    url = "https://api.line.me/v2/bot/profile"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            profile = response.json()
            print(f"✅ Line Bot 連接成功")
            print(f"🤖 Bot 名稱: {profile.get('displayName', 'N/A')}")
            print(f"📝 Bot 描述: {profile.get('statusMessage', 'N/A')}")
            return True
        else:
            print(f"❌ 連接失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 連接錯誤: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Line 群組 ID 獲取工具")
    print("=" * 50)
    
    # 測試連接
    if test_line_connection():
        print("\n" + "=" * 50)
        # 獲取群組 ID
        group_id = get_line_group_id()
        
        if group_id:
            print("\n🎉 成功獲取群組 ID！")
            print(f"📋 請在 Render 環境變數中設定：")
            print(f"LINE_GROUP_ID={group_id}")
        else:
            print("\n💡 如果沒有找到群組 ID，請：")
            print("1. 確保 Line Bot 已加入群組")
            print("2. 在群組中發送任意訊息")
            print("3. 等待 1-2 分鐘後重新運行此腳本")
    else:
        print("\n❌ 無法連接到 Line Bot")
        print("請檢查 LINE_CHANNEL_ACCESS_TOKEN 是否正確") 