from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'khoa_bi_mat_cho_demo_mon_hoc_123' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    categories = db.relationship('Category', backref='user', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='category', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.Date, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại!', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='scrypt')
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        default_cats = [
            ('Lương', 'income'), ('Thưởng', 'income'),
            ('Ăn uống', 'expense'), ('Đi lại', 'expense'), ('Nhà cửa', 'expense')
        ]
        for name, type_ in default_cats:
            db.session.add(Category(name=name, type=type_, user_id=new_user.id))
        db.session.commit()
        
        flash('Đăng ký thành công! Hãy đăng nhập.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    
    total_income = sum(t.amount for t in transactions if t.category.type == 'income')
    total_expense = sum(t.amount for t in transactions if t.category.type == 'expense')
    balance = total_income - total_expense

    expense_cats = {}
    for t in transactions:
        if t.category.type == 'expense':
            if t.category.name in expense_cats:
                expense_cats[t.category.name] += t.amount
            else:
                expense_cats[t.category.name] = t.amount
    
    chart_labels = list(expense_cats.keys())
    chart_data = list(expense_cats.values())

    return render_template('dashboard.html', 
                           transactions=transactions, 
                           total_income=total_income, 
                           total_expense=total_expense, 
                           balance=balance,
                           chart_labels=json.dumps(chart_labels),
                           chart_data=json.dumps(chart_data))

# --- CHỨC NĂNG THÊM MỚI ---
@app.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        desc = request.form.get('description')
        date_str = request.form.get('date')
        cat_id = int(request.form.get('category'))
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        new_trans = Transaction(amount=amount, description=desc, date=date_obj, category_id=cat_id, user_id=current_user.id)
        db.session.add(new_trans)
        db.session.commit()
        flash('Thêm giao dịch thành công!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('add_edit.html', categories=categories, title="Thêm Giao dịch", transaction=None)

# --- CHỨC NĂNG SỬA (MỚI) ---
@app.route('/edit_transaction/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if transaction.user_id != current_user.id:
        flash('Bạn không có quyền sửa giao dịch này!', 'danger')
        return redirect(url_for('dashboard'))

    categories = Category.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        transaction.amount = float(request.form.get('amount'))
        transaction.description = request.form.get('description')
        date_str = request.form.get('date')
        transaction.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        transaction.category_id = int(request.form.get('category'))

        db.session.commit()
        flash('Cập nhật thành công!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_edit.html', categories=categories, title="Sửa Giao dịch", transaction=transaction)

@app.route('/delete/<int:id>')
@login_required
def delete_transaction(id):
    trans = Transaction.query.get_or_404(id)
    if trans.user_id == current_user.id:
        db.session.delete(trans)
        db.session.commit()
        flash('Đã xóa giao dịch', 'warning')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)