from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import pytz
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import gridfs

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

# 允許的檔案類型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

# 路由
@app.route('/')
def index():
    events = list(events_collection.find().sort('start_date', 1))
    for event in events:
        # 獲取報名人數
        event['registrations'] = list(registrations_collection.find({'event_id': event['_id']}))
    return render_template('index.html', events=events)

@app.route('/event/<event_id>')
def event_detail(event_id):
    try:
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))
        
        registrations = list(registrations_collection.find({'event_id': ObjectId(event_id)}))
        return render_template('event_detail.html', event=event, registrations=registrations)
    except Exception as e:
        flash('無效的活動 ID')
        return redirect(url_for('index'))

@app.route('/event/<event_id>/registration/<registration_id>/cancel', methods=['POST'])
def cancel_registration(event_id, registration_id):
    try:
        # 檢查活動是否存在
        event = events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            flash('活動不存在')
            return redirect(url_for('index'))
        
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
            required_fields = ['name', 'email', 'phone']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'請填寫{field}欄位')
                    return render_template('register.html', event=event)

            registration_data = {
                'event_id': ObjectId(event_id),
                'name': request.form['name'],
                'email': request.form['email'],
                'phone': request.form['phone'],
                'registration_time': datetime.now(pytz.timezone('Asia/Taipei'))
            }
            
            # 處理自定義欄位
            custom_fields = {}
            if event.get('custom_fields'):
                for field in event['custom_fields']:
                    custom_fields[field['name']] = request.form.get(field['name'], '')
            registration_data['custom_fields'] = custom_fields
            
            try:
                registrations_collection.insert_one(registration_data)
                flash('報名成功！')
                return redirect(url_for('event_detail', event_id=event_id))
            except Exception as e:
                print(f"Error saving registration: {str(e)}")
                flash('報名時發生錯誤，請稍後再試')
                return render_template('register.html', event=event)
        
        return render_template('register.html', event=event)
    except Exception as e:
        print(f"Error in registration process: {str(e)}")
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
        flash('無權限訪問此頁面')
        return redirect(url_for('index'))
    
    events = list(events_collection.find().sort('start_date', 1))
    for event in events:
        # 獲取報名人數
        event['registrations'] = list(registrations_collection.find({'event_id': event['_id']}))
        # 確保每個活動都有 fee 欄位
        if 'fee' not in event:
            event['fee'] = 0
    return render_template('admin/index.html', events=events)

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
        
        custom_fields = []
        for i in range(len(field_names)):
            if field_names[i]:  # 只處理有名稱的欄位
                field = {
                    'name': field_names[i],
                    'type': field_types[i],
                }
                if field_types[i] in ['radio', 'checkbox'] and field_options[i]:
                    field['options'] = [opt.strip() for opt in field_options[i].split(',')]
                custom_fields.append(field)

        event_data = {
            'title': request.form['title'],
            'description': request.form['description'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'meeting_time': request.form['meeting_time'],
            'location': request.form['location'],
            'fee': int(request.form['fee']),
            'organizer': request.form['organizer'],
            'co_organizers': [line.strip() for line in request.form['co_organizers'].split('\n') if line.strip()],
            'custom_fields': custom_fields,
            'notes_label': request.form.get('notes_label', ''),
            'reference_files': []
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
        
        if request.method == 'POST':
            # 處理自訂欄位
            field_names = request.form.getlist('field_names[]')
            field_types = request.form.getlist('field_types[]')
            field_options = request.form.getlist('field_options[]')
            
            custom_fields = []
            for i in range(len(field_names)):
                if field_names[i]:  # 只處理有名稱的欄位
                    field = {
                        'name': field_names[i],
                        'type': field_types[i],
                    }
                    if field_types[i] in ['radio', 'checkbox'] and field_options[i]:
                        field['options'] = [opt.strip() for opt in field_options[i].split(',')]
                    custom_fields.append(field)

            event_data = {
                'title': request.form['title'],
                'description': request.form['description'],
                'start_date': request.form['start_date'],
                'end_date': request.form['end_date'],
                'meeting_time': request.form['meeting_time'],
                'location': request.form['location'],
                'fee': int(request.form['fee']),
                'organizer': request.form['organizer'],
                'co_organizers': [line.strip() for line in request.form['co_organizers'].split('\n') if line.strip()],
                'custom_fields': custom_fields,
                'notes_label': request.form.get('notes_label', ''),
                'reference_files': event.get('reference_files', [])
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

@app.route('/download/<file_id>')
def download_file(file_id):
    try:
        file_data = fs.get(ObjectId(file_id))
        return send_file(
            file_data,
            download_name=file_data.filename,
            as_attachment=True
        )
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        flash('下載檔案時發生錯誤')
        return redirect(url_for('index'))

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

# 創建管理員帳號
def create_admin():
    try:
        admin = users_collection.find_one({'username': 'admin'})
        if not admin:
            result = users_collection.insert_one({
                'username': 'admin',
                'password': 'admin123',  # 請更改為安全的密碼
                'is_admin': True
            })
            print("Admin account created successfully!")
            return True
        else:
            print("Admin account already exists!")
            return True
    except Exception as e:
        print(f"Error creating admin account: {str(e)}")
        return False

if __name__ == '__main__':
    # 創建管理員帳號
    create_admin()
    app.run(debug=True)
else:
    # 在 production 環境中也創建管理員帳號
    success = create_admin()
    if not success:
        print("Failed to create admin account!")
