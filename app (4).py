from flask import Flask, session, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from wtforms import Form, StringField, PasswordField, validators
from markupsafe import Markup
from jinja2 import Template

# --- Import your models ---
from models import (
    db, Product, Transaction, TransactionItem,
    Ledger, JurnalUmum, NeracaSaldoAwal, NeracaSaldo,
    TransactionView
)

# --- Flask app setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# --- WTForms login form ---
class LoginForm(Form):
    username = StringField('Username', [validators.InputRequired()])
    password = PasswordField('Password', [validators.InputRequired()])


# --- Custom Admin Home (not used for landing anymore) ---
class MyAdminHome(AdminIndexView):
    @expose('/')
    def index(self):
        return super().render('admin/index.html')


# --- Login View ---
class LoginView(BaseView):
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        form = LoginForm(request.form)
        if request.method == 'POST' and form.validate():
            if form.username.data == 'admin' and form.password.data == 'password':
                session['logged_in'] = True
                flash('Login berhasil!', 'success')
                return redirect('/landing')  # ✅ Go to landing screen after login
            else:
                flash('Username atau password salah.', 'error')
        return super().render('admin/model/edit.html', form=form)


# --- Logout View ---
class LogoutView(BaseView):
    @expose('/')
    def index(self):
        session.pop('logged_in', None)
        flash('Logout berhasil.', 'info')
        return redirect(url_for('login.index'))


# --- Protected Admin Views ---
class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('logged_in', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login.index'))


class SecureTransactionView(TransactionView):
    def is_accessible(self):
        return session.get('logged_in', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login.index'))


# --- Flask-Admin Setup ---
admin = Admin(app, name='SIM Admin', index_view=MyAdminHome(), template_mode='bootstrap4')
admin.add_view(LoginView(name='Login', endpoint='login'))
admin.add_view(LogoutView(name='Logout', endpoint='logout'))

admin.add_view(SecureModelView(Product, db.session))
admin.add_view(SecureTransactionView(Transaction, db.session))
admin.add_view(SecureModelView(Ledger, db.session))
admin.add_view(SecureModelView(JurnalUmum, db.session))
admin.add_view(SecureModelView(NeracaSaldoAwal, db.session))
admin.add_view(SecureModelView(NeracaSaldo, db.session))


# --- Public Landing Page at `/` ---
@app.route('/')
def welcome_page():
    html_template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Selamat Datang</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {
                background-color: #001f3f;
                font-family: 'Segoe UI', sans-serif;
                text-align: center;
                color: white;
                padding-top: 100px;
            }
            .logo {
                width: 120px;
                margin-bottom: 20px;
            }
            .btn-custom {
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <img src="/static/images/logo_warsito.jpg" class="logo" alt="Logo">
        <h2>Selamat Datang di Aplikasi SIM Admin</h2>
        <p>Silakan klik tombol di bawah untuk masuk.</p>
        <a href="/admin/login" class="btn btn-light btn-custom">Login Admin</a>
    </body>
    </html>
    """)
    return html_template.render()


# --- Post-login Landing Page ---
@app.route('/landing')
def landing_page():
    if not session.get('logged_in'):
        return redirect('/admin/login')

    html_template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Welcome</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {
                background-color: #001f3f;
                font-family: 'Segoe UI', sans-serif;
                text-align: center;
                color: white;
                padding-top: 100px;
            }
            .logo {
                width: 120px;
                margin-bottom: 20px;
            }
            .btn-custom {
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <img src="/static/images/logo_warsito.jpg" class="logo" alt="Logo">
        <h2>Selamat Datang di SIM Admin</h2>
        <p>Login berhasil. Gunakan tombol di bawah untuk masuk ke sistem admin.</p>
        <a href="/admin" class="btn btn-light btn-custom">Masuk ke Admin</a>
    </body>
    </html>
    """)
    return html_template.render()


# --- Run Server ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
