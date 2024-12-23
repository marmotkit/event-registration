from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# 設定 MongoDB
client = MongoClient(os.getenv('MONGODB_URI'))
db = client.event_registration
events_collection = db.events
users_collection = db.users
registrations_collection = db.registrations

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
    events = list(events_collection.find())
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
                'registration_time': datetime.utcnow()
            }
            
            # 處理自定義欄位
            custom_fields = {}
            if event.get('custom_fields'):
                for field in event['custom_fields']:
                    custom_fields[field] = request.form.get(field, '')
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
    
    events = list(events_collection.find())
    # 為每個活動添加報名人數
    for event in events:
        event['registration_count'] = registrations_collection.count_documents({'event_id': event['_id']})
    
    return render_template('admin/index.html', events=events)

@app.route('/admin/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    if not current_user.is_admin:
        flash('無權限訪問此頁面')
        return redirect(url_for('index'))

    if request.method == 'POST':
        event_data = {
            'title': request.form['title'],
            'description': request.form['description'],
            'date': request.form['date'],
            'location': request.form['location'],
            'custom_fields': request.form.getlist('custom_fields'),
            'created_at': datetime.now().isoformat()
        }
        result = events_collection.insert_one(event_data)
        flash('活動建立成功！')
        return redirect(url_for('admin'))
    
    return render_template('admin/event_form.html')

@app.route('/admin/event/<event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if not current_user.is_admin:
        flash('無權限訪問此頁面')
        return redirect(url_for('index'))

    event = events_collection.find_one({'_id': ObjectId(event_id)})
    if not event:
        flash('活動不存在')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        event_data = {
            'title': request.form['title'],
            'description': request.form['description'],
            'date': request.form['date'],
            'location': request.form['location'],
            'custom_fields': request.form.getlist('custom_fields'),
            'created_at': event['created_at']
        }
        events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': event_data}
        )
        flash('活動更新成功！')
        return redirect(url_for('admin'))
    
    return render_template('admin/event_form.html', event=event)

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
