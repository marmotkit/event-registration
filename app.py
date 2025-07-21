from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import pytz
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import gridfs
import io
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上傳檔案大小為 16MB

# 設定 MongoDB
client = MongoClient(os.getenv('MONGODB_URI'))
db = client.event_registration
events_collection = db.events
users_collection = db.users
registrations_collection = db.registrations
fs = gridfs.GridFS(db)  # 用於存儲檔案

# 設定 Line Bot
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN', ''))
line_handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET', ''))

# 允許的檔案類型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_registration_list_for_line(event, registrations):
    """格式化報名名單用於發送到 Line 群組"""
    if not registrations:
        return f"📋 {event['title']}\n\n目前尚無報名者"
    
    # 計算統計資訊
    total_participants = sum(int(reg.get('participants', 1)) for reg in registrations)
    paid_count = sum(1 for reg in registrations if reg.get('has_paid', False))
    
    message = f"📋 {event['title']}\n"
    message += f"📅 活動日期：{event['start_date']}"
    if event['start_date'] != event['end_date']:
        message += f" 至 {event['end_date']}"
    message += f"\n📍 地點：{event['location']}\n"
    message += f"💰 費用：NT$ {event['fee']}\n\n"
    
    message += f"📊 報名統計：\n"
    message += f"• 報名人數：{len(registrations)} 人\n"
    message += f"• 總參與人數：{total_participants} 人\n"
    message += f"• 已繳費：{paid_count} 人\n"
    message += f"• 已收費用：NT$ {paid_count * event['fee']}\n\n"
    
    message += "📝 報名名單：\n"
    for i, reg in enumerate(registrations, 1):
        message += f"{i}. {reg['name']}"
        if reg.get('phone'):
            message += f" ({reg['phone']})"
        if reg.get('participants') and reg['participants'] != '1':
            message += f" x{reg['participants']}人"
        if reg.get('has_paid'):
            message += " ✅已繳費"
        message += f"\n"
    
    return message

def send_registration_update_to_line(event_id):
    """發送報名更新到 Line 群組"""
    try:
        # 獲取 Line 群組 ID
        line_group_id = os.getenv('LINE_GROUP_ID')
        if not line_group_id:
            print("LINE_GROUP_ID 未設定，跳過發送 Line 訊息")
            return
        
        # 獲取活動資訊
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            print(f"找不到活動 {event_id}")
            return
        
        # 獲取報名資料
        registrations = list(registrations_collection.find({'event_id': ObjectId(event_id)}))
        
        # 格式化訊息
        message = format_registration_list_for_line(event, registrations)
        
        # 發送到 Line 群組
        line_bot_api.push_message(line_group_id, TextSendMessage(text=message))
        print(f"已發送報名更新到 Line 群組：{event['title']}")
        
    except Exception as e:
        print(f"發送 Line 訊息時發生錯誤：{str(e)}")

# 防止快取
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# 添加時間戳到所有模板
@app.context_processor
def inject_timestamp():
    return {'timestamp': datetime.now().timestamp()}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        
    def get_id(self):
        return str(self.user_data['_id'])
    
    @property
    def is_admin(self):
        return self.user_data.get('is_admin', False)

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

# 清理自定義欄位，移除與預設欄位重複的欄位
def clean_custom_fields(custom_fields):
    if not custom_fields:
        return []
    
    # 預設欄位名稱
    reserved_fields = ['姓名', '電話', '電子郵件', 'email', 'phone', 'name']
    
    # 過濾掉預設欄位
    cleaned_fields = [
        field for field in custom_fields 
        if field.get('name', '').lower() not in [f.lower() for f in reserved_fields]
    ]
    
    return cleaned_fields

# 路由
@app.route('/')
def index():
    try:
        # 根據用戶權限過濾活動
        query = {}
        if not current_user.is_authenticated or not current_user.user_data.get('can_hide_events', False):
            query['is_hidden'] = {'$ne': True}
        
        events = list(events_collection.find(query).sort('start_date', -1))
        
        # 對每個活動添加報名人數統計
        for event in events:
            # 獲取報名資料
            registrations = list(registrations_collection.find({'event_id': event['_id']}))
            event['registration_count'] = len(registrations)
            
            # 計算已繳費人數和金額
            paid_count = sum(1 for reg in registrations if reg.get('has_paid', False))
            event['paid_count'] = paid_count
            event['paid_amount'] = paid_count * event.get('fee', 0)
            event['total_amount'] = event['registration_count'] * event.get('fee', 0)
        
        return render_template('index.html', events=events)
    except Exception as e:
        print(f"Error in index: {str(e)}")
        flash('載入活動列表時發生錯誤')
        return render_template('index.html', events=[])

@app.route('/event/<event_id>')
def event_detail(event_id):
    try:
        # 先嘗試使用 ObjectId 查詢
        try:
            event = events_collection.find_one({'_id': ObjectId(event_id)})
        except:
            flash('無效的活動 ID')
            return redirect(url_for('index'))
        
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))
        
        # 檢查活動是否被鎖定且用戶未登入或非管理員
        if event.get('is_locked', False) and (
            not current_user.is_authenticated or 
            not getattr(current_user, 'user_data', {}).get('can_hide_events', False)
        ):
            flash('此活動已被鎖定')
            return redirect(url_for('index'))
        
        # 確保 event 有 custom_fields 屬性
        if 'custom_fields' not in event:
            event['custom_fields'] = []
        
        # 獲取報名資料
        try:
            registrations = list(registrations_collection.find({
                'event_id': ObjectId(event_id)
            }))
        except:
            registrations = []
        
        # 確保每個報名記錄都有必要的屬性
        for reg in registrations:
            if 'register_time' not in reg:
                reg['register_time'] = '未記錄'
            if 'custom_fields' not in reg:
                reg['custom_fields'] = {}
        
        event['registration_count'] = len(registrations)
        
        # 計算已繳費人數和金額
        paid_count = sum(1 for reg in registrations if reg.get('has_paid', False))
        event['paid_count'] = paid_count
        event['paid_amount'] = paid_count * event.get('fee', 0)
        event['total_amount'] = event['registration_count'] * event.get('fee', 0)
        
        return render_template('event_detail.html', event=event, registrations=registrations)
    except Exception as e:
        print(f"Error in event_detail: {str(e)}")
        flash('系統錯誤')
        return redirect(url_for('index'))

@app.route('/event/<event_id>/cancel_registration/<registration_id>', methods=['POST'])
def cancel_registration(event_id, registration_id):
    try:
        # 檢查活動是否存在
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))
        
        # 檢查活動是否被鎖定
        if event.get('is_locked', False) and not current_user.user_data.get('can_hide_events', False):
            flash('此活動已被鎖定，無法修改')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # 檢查報名記錄是否存在
        registration = registrations_collection.find_one({
            '_id': ObjectId(registration_id),
            'event_id': ObjectId(event_id)
        })
        
        if not registration:
            flash('報名記錄不存在')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # 刪除報名記錄
        registrations_collection.delete_one({'_id': ObjectId(registration_id)})
        
        # 發送報名更新到 Line 群組
        send_registration_update_to_line(str(event_id))
        
        flash('已取消報名')
        
        return redirect(url_for('event_detail', event_id=event_id))
    except Exception as e:
        print(f"Error canceling registration: {str(e)}")
        flash('取消報名時發生錯誤')
        return redirect(url_for('event_detail', event_id=event_id))

@app.route('/register/<event_id>', methods=['GET', 'POST'])
def register(event_id):
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))

        if request.method == 'POST':
            # 驗證必填欄位
            required_fields = ['name']  # 只有姓名是必填
            
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'{field} 是必填欄位')
                    return render_template('register.html', event=event)

            # 處理報名資料
            registration_data = {
                'event_id': ObjectId(event_id),
                'name': request.form['name'],
                'phone': request.form.get('phone', ''),
                'email': request.form.get('email', ''),
                'participants': request.form.get('participants', ''),
                'preferred_date': request.form.get('preferred_date', ''),
                'register_time': datetime.now().strftime('%Y-%m-%d'),  # 只保留日期
                'has_paid': False
            }

            try:
                registrations_collection.insert_one(registration_data)
                
                # 發送報名更新到 Line 群組
                send_registration_update_to_line(str(event_id))
                
                flash('報名成功！')
                return redirect(url_for('event_detail', event_id=event_id))
            except Exception as e:
                print(f"Error saving registration: {str(e)}")
                flash('報名時發生錯誤，請稍後再試')
                return render_template('register.html', event=event)

        return render_template('register.html', event=event)
    except Exception as e:
        print(f"Error in register: {str(e)}")
        flash('無效的活動 ID')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user_data = users_collection.find_one({'username': username})
        
        if user_data and user_data['password'] == password:
            user = User(user_data)
            login_user(user)
            return redirect(url_for('admin' if user.is_admin else 'index'))
        
        flash('帳號或密碼錯誤')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('您沒有權限訪問此頁面')
        return redirect(url_for('index'))
    
    try:
        # 根據用戶權限過濾活動
        query = {}
        if not current_user.user_data.get('can_hide_events', False):
            query['is_hidden'] = {'$ne': True}
        
        events = list(events_collection.find(query).sort('start_date', -1))
        
        # 對每個活動添加報名和費用統計
        for event in events:
            # 獲取報名資料
            registrations = list(registrations_collection.find({'event_id': event['_id']}))
            event['registrations'] = registrations
            event['registration_count'] = len(registrations)
            
            # 計算已繳費人數和金額
            paid_count = sum(1 for reg in registrations if reg.get('has_paid', False))
            event['paid_count'] = paid_count
            event['paid_amount'] = paid_count * event.get('fee', 0)
            event['total_amount'] = event['registration_count'] * event.get('fee', 0)
            
            # 修改報名時間格式
            for reg in registrations:
                if 'register_time' in reg:
                    reg['timestamp'] = reg['register_time']
        
        return render_template('admin.html', events=events)
    except Exception as e:
        print(f"Error in admin: {str(e)}")
        flash('載入活動列表時發生錯誤')
        return render_template('admin.html', events=[])

@app.route('/admin/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    if not current_user.is_admin:
        flash('您沒有權限訪問此頁面')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 處理自訂欄位
        field_names = request.form.getlist('field_names[]')
        field_types = request.form.getlist('field_types[]')
        field_options = request.form.getlist('field_options[]')
        
        # 預設欄位名稱，這些欄位不能被重複添加
        reserved_fields = ['姓名', '電話', '電子郵件', 'email', 'phone', 'name']
        
        custom_fields = []
        for i in range(len(field_names)):
            if field_names[i]:  # 只處理有名稱的欄位
                field_name = field_names[i].strip()
                # 檢查是否是預設欄位
                if field_name.lower() not in [f.lower() for f in reserved_fields]:
                    field = {
                        'name': field_name,
                        'type': field_types[i],
                    }
                    if field_types[i] in ['radio', 'checkbox'] and field_options[i]:
                        field['options'] = [opt.strip() for opt in field_options[i].split(',')]
                    custom_fields.append(field)

        # 處理協辦人員
        co_organizers = [line.strip() for line in request.form['co_organizers'].split('\n') if line.strip()]

        event_data = {
            'title': request.form['title'],
            'description': request.form['description'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'meeting_time': request.form['meeting_time'],
            'location': request.form['location'],
            'fee': int(request.form['fee']),
            'organizer': request.form['organizer'],
            'co_organizers': co_organizers,
            'custom_fields': custom_fields,
            'notes_label': request.form.get('notes_label', ''),
            'reference_files': [],
            'is_hidden': False,
            'is_locked': False  # 新增活動預設為未鎖定
        }

        # 處理檔案上傳
        if 'reference_files' in request.files:
            files = request.files.getlist('reference_files')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_id = fs.put(file, filename=filename)
                    event_data['reference_files'].append({
                        '_id': file_id,
                        'filename': filename
                    })

        try:
            events_collection.insert_one(event_data)
            flash('活動建立成功！')
            return redirect(url_for('admin'))
        except Exception as e:
            print(f"Error creating event: {str(e)}")
            flash('建立活動時發生錯誤，請稍後再試')

    return render_template('event_form.html', event={}, is_new=True)

@app.route('/admin/event/<event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if not current_user.is_admin:
        flash('您沒有權限訪問此頁面')
        return redirect(url_for('index'))
    
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('admin'))
        
        # 檢查活動是否被鎖定
        if event.get('is_locked', False) and not current_user.user_data.get('can_hide_events', False):
            flash('此活動已被鎖定，無法修改')
            return redirect(url_for('admin'))
        
        if request.method == 'POST':
            # 處理自訂欄位
            field_names = request.form.getlist('field_names[]')
            field_types = request.form.getlist('field_types[]')
            field_options = request.form.getlist('field_options[]')
            
            custom_fields = []
            for i in range(len(field_names)):
                if field_names[i]:  # 只處理有名稱的欄位
                    field_name = field_names[i].strip()
                    field = {
                        'name': field_name,
                        'type': field_types[i],
                    }
                    if field_types[i] in ['radio', 'checkbox'] and field_options[i]:
                        field['options'] = [opt.strip() for opt in field_options[i].split(',')]
                    custom_fields.append(field)

            # 清理自定義欄位
            custom_fields = clean_custom_fields(custom_fields)

            # 處理協辦人員
            co_organizers = [line.strip() for line in request.form['co_organizers'].split('\n') if line.strip()]
            
            event_data = {
                'title': request.form['title'],
                'description': request.form['description'],
                'start_date': request.form['start_date'],
                'end_date': request.form['end_date'],
                'meeting_time': request.form['meeting_time'],
                'location': request.form['location'],
                'fee': int(request.form['fee']),
                'organizer': request.form['organizer'],
                'co_organizers': co_organizers,
                'custom_fields': custom_fields,
                'notes_label': request.form.get('notes_label', ''),
                'reference_files': event.get('reference_files', []),
                'is_hidden': event.get('is_hidden', False)
            }

            # 處理檔案上傳
            if 'reference_files' in request.files:
                files = request.files.getlist('reference_files')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        file_id = fs.put(file, filename=filename)
                        event_data['reference_files'].append({
                            '_id': file_id,
                            'filename': filename
                        })

            try:
                events_collection.update_one(
                    {'_id': ObjectId(event_id)},
                    {'$set': event_data}
                )
                flash('活動更新成功！')
                return redirect(url_for('admin'))
            except Exception as e:
                print(f"Error updating event: {str(e)}")
                flash('更新活動時發生錯誤，請稍後再試')

        # 清理自定義欄位
        event['custom_fields'] = clean_custom_fields(event.get('custom_fields', []))
        return render_template('event_form.html', event=event, is_new=False)
    except Exception as e:
        print(f"Error in edit_event: {str(e)}")
        flash('無效的活動 ID')
        return redirect(url_for('admin'))

@app.route('/admin/event/<event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    if not current_user.is_admin:
        flash('無權限訪問此頁面')
        return redirect(url_for('index'))

    try:
        # 刪除活動
        result = events_collection.delete_one({'_id': ObjectId(event_id)})
        if result.deleted_count > 0:
            # 刪除相關的報名記錄
            registrations_collection.delete_many({'event_id': ObjectId(event_id)})
            flash('活動已成功刪除')
        else:
            flash('找不到要刪除的活動')
    except Exception as e:
        flash('刪除活動時發生錯誤')
        print(f"Error deleting event: {str(e)}")
    
    return redirect(url_for('admin'))

@app.route('/event/<event_id>/file/<file_id>')
def download_file(event_id, file_id):
    try:
        # 確保 ObjectId 格式正確
        event_id = ObjectId(event_id)
        file_id = ObjectId(file_id)
        
        # 獲取活動資訊
        event = events_collection.find_one({'_id': event_id})
        if not event:
            flash('找不到活動')
            return redirect(url_for('index'))
            
        # 在活動的檔案列表中尋找指定檔案
        file_info = None
        for file in event.get('reference_files', []):
            if file.get('_id') == file_id:
                file_info = file
                break
                
        if not file_info:
            flash('找不到檔案')
            return redirect(url_for('view_event', event_id=event_id))
            
        # 從 GridFS 獲取檔案
        grid_file = fs.get(file_id)
        
        if not grid_file:
            flash('找不到檔案')
            return redirect(url_for('view_event', event_id=event_id))
            
        # 設置回應標頭
        response = send_file(
            io.BytesIO(grid_file.read()),
            mimetype=grid_file.content_type,
            as_attachment=True,
            download_name=file_info['filename']
        )
        
        return response
        
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        flash('下載檔案時發生錯誤')
        return redirect(url_for('view_event', event_id=event_id))

@app.route('/admin/event/<event_id>/file/<file_id>/delete', methods=['POST'])
@login_required
def delete_file(event_id, file_id):
    if not current_user.is_admin:
        flash('您沒有權限執行此操作')
        return redirect(url_for('index'))
    
    try:
        # 從活動中移除檔案記錄
        events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$pull': {'reference_files': {'_id': ObjectId(file_id)}}}
        )
        
        # 從 GridFS 中刪除檔案
        fs.delete(ObjectId(file_id))
        
        flash('檔案已刪除')
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
        flash('刪除檔案時發生錯誤')
    
    return redirect(url_for('edit_event', event_id=event_id))

@app.route('/admin/event/<event_id>')
@login_required
def view_event(event_id):
    if not current_user.is_admin:
        flash('您沒有權限訪問此頁面')
        return redirect(url_for('index'))
    
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('admin'))

        # 獲取報名資料
        registrations = list(registrations_collection.find({'event_id': ObjectId(event_id)}))
        event['registrations'] = registrations
        event['registration_count'] = len(registrations)
        
        # 計算已繳費人數和金額
        paid_count = sum(1 for reg in registrations if reg.get('has_paid', False))
        event['paid_count'] = paid_count
        event['paid_amount'] = paid_count * event.get('fee', 0)
        event['total_amount'] = event['registration_count'] * event.get('fee', 0)
        
        return render_template('view_event.html', event=event)
    except Exception as e:
        print(f"Error in view_event: {str(e)}")
        flash('無效的活動 ID')
        return redirect(url_for('admin'))

@app.route('/admin/registration/<registration_id>/toggle_payment', methods=['POST'])
@login_required
def toggle_payment(registration_id):
    if not current_user.is_admin:
        return jsonify({'error': '您沒有權限執行此操作'}), 403
    
    try:
        registration = registrations_collection.find_one({'_id': ObjectId(registration_id)})
        if not registration:
            return jsonify({'error': '找不到報名記錄'}), 404

        # 切換繳費狀態
        new_status = not registration.get('has_paid', False)
        registrations_collection.update_one(
            {'_id': ObjectId(registration_id)},
            {'$set': {'has_paid': new_status}}
        )
        
        # 發送報名更新到 Line 群組
        send_registration_update_to_line(str(registration['event_id']))
        
        return jsonify({
            'success': True,
            'has_paid': new_status
        })
    except Exception as e:
        print(f"Error toggling payment status: {str(e)}")
        return jsonify({'error': '更新繳費狀態時發生錯誤'}), 500

@app.route('/admin/event/<event_id>/registrations')
@login_required
def get_event_registrations(event_id):
    if not current_user.is_admin:
        return jsonify({'error': '您沒有權限訪問此頁面'}), 403
    
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            return jsonify({'error': '活動不存在'}), 404

        # 確保 event 有 custom_fields 屬性
        if 'custom_fields' not in event:
            event['custom_fields'] = []

        # 獲取報名資料
        registrations = list(registrations_collection.find({'event_id': ObjectId(event_id)}))
        
        # 確保每個報名記錄都有必要的屬性
        for reg in registrations:
            if 'register_time' not in reg:
                reg['register_time'] = '未記錄'
            if 'custom_fields' not in reg:
                reg['custom_fields'] = {}
        
        return render_template('_registration_list.html', event=event, registrations=registrations)
    except Exception as e:
        print(f"Error in get_event_registrations: {str(e)}")
        return jsonify({'error': '載入報名名單時發生錯誤'}), 500

@app.route('/event/<event_id>/edit_registration/<registration_id>', methods=['POST'])
def edit_registration(event_id, registration_id):
    try:
        # 檢查活動是否存在
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))
        
        # 檢查活動是否被鎖定
        if event.get('is_locked', False) and not current_user.user_data.get('can_hide_events', False):
            flash('此活動已被鎖定，無法修改')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # 檢查報名記錄是否存在
        registration = registrations_collection.find_one({
            '_id': ObjectId(registration_id),
            'event_id': ObjectId(event_id)
        })
        
        if not registration:
            flash('報名記錄不存在')
            return redirect(url_for('event_detail', event_id=event_id))
        
        # 更新報名資料
        updated_data = {
            'name': request.form['name'],
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', ''),
            'participants': request.form.get('participants', '1'),
            'custom_fields': {}
        }
        
        # 處理自訂欄位
        for field in event.get('custom_fields', []):
            field_name = field['name']
            field_value = request.form.get(f'custom_fields[{field_name}]', '')
            updated_data['custom_fields'][field_name] = field_value
        
        registrations_collection.update_one(
            {'_id': ObjectId(registration_id)},
            {'$set': updated_data}
        )
        
        # 發送報名更新到 Line 群組
        send_registration_update_to_line(str(event_id))
        
        flash('報名資料已更新')
        return redirect(url_for('event_detail', event_id=event_id))
        
    except Exception as e:
        print(f"Error editing registration: {str(e)}")
        flash('修改報名資料時發生錯誤')
        return redirect(url_for('event_detail', event_id=event_id))

# 創建管理員帳號
def create_admin():
    try:
        # 創建 admin 賬號
        admin = users_collection.find_one({'username': 'admin'})
        if not admin:
            users_collection.insert_one({
                'username': 'admin',
                'password': 'admin123',
                'is_admin': True,
                'can_hide_events': False  # 普通管理員不能隱藏活動
            })
            print("Admin account created successfully!")
        
        # 創建 kt 賬號
        kt = users_collection.find_one({'username': 'kt'})
        if not kt:
            users_collection.insert_one({
                'username': 'kt',
                'password': 'kingmax00',
                'is_admin': True,
                'can_hide_events': True  # kt 可以隱藏活動
            })
            print("KT account created successfully!")
        
        return True
    except Exception as e:
        print(f"Error creating admin accounts: {str(e)}")
        return False

# 添加隱藏活動的路由
@app.route('/admin/event/<event_id>/toggle_visibility', methods=['POST'])
@login_required
def toggle_event_visibility(event_id):
    if not current_user.user_data.get('can_hide_events', False):
        return jsonify({'error': '您沒有權限執行此操作'}), 403
    
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            return jsonify({'error': '活動不存在'}), 404

        # 切換隱藏狀態
        new_status = not event.get('is_hidden', False)
        events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': {'is_hidden': new_status}}
        )
        
        return jsonify({
            'success': True,
            'is_hidden': new_status
        })
    except Exception as e:
        print(f"Error toggling event visibility: {str(e)}")
        return jsonify({'error': '更新活動狀態時發生錯誤'}), 500

# 添加活動鎖定的路由
@app.route('/admin/event/<event_id>/toggle_lock', methods=['POST'])
@login_required
def toggle_event_lock(event_id):
    if not current_user.user_data.get('can_hide_events', False):  # 使用相同的權限檢查
        return jsonify({'error': '您沒有權限執行此操作'}), 403
    
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            return jsonify({'error': '活動不存在'}), 404

        # 切換鎖定狀態
        new_status = not event.get('is_locked', False)
        events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': {'is_locked': new_status}}
        )
        
        return jsonify({
            'success': True,
            'is_locked': new_status
        })
    except Exception as e:
        print(f"Error toggling event lock: {str(e)}")
        return jsonify({'error': '更新活動狀態時發生錯誤'}), 500

@app.route('/line/webhook', methods=['POST'])
def line_webhook():
    """Line Bot Webhook 處理"""
    try:
        # 獲取 X-Line-Signature 標頭
        signature = request.headers['X-Line-Signature']
        
        # 獲取請求體
        body = request.get_data(as_text=True)
        
        # 記錄 webhook 事件（用於調試）
        print(f"收到 Line webhook: {body}")
        
        # 驗證簽名
        line_handler.handle(body, signature)
        
        return 'OK'
    except InvalidSignatureError:
        print("Invalid signature")
        return 'Invalid signature', 400
    except Exception as e:
        print(f"Line webhook error: {str(e)}")
        return 'Error', 500

@app.route('/line/test', methods=['GET'])
def line_test():
    """測試 Line Bot 連接和獲取群組 ID"""
    try:
        # 測試 Line Bot 連接
        profile = line_bot_api.get_profile('U1234567890abcdef1234567890abcdef')  # 使用假 ID 測試連接
        return jsonify({
            'status': 'success',
            'message': 'Line Bot 連接正常',
            'note': '請在群組中發送訊息，然後查看應用程式日誌來獲取群組 ID'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Line Bot 連接失敗: {str(e)}',
            'note': '請檢查 LINE_CHANNEL_ACCESS_TOKEN 是否正確'
        })

if __name__ == '__main__':
    # 創建管理員帳號
    create_admin()
    app.run(debug=True)
else:
    # 在 production 環境中也創建管理員帳號
    success = create_admin()
    if not success:
        print("Failed to create admin account!")
