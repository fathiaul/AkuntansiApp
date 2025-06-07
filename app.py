# app.py

from flask import Flask, session, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_admin.form.widgets import DatePickerWidget
from wtforms import Form, StringField, PasswordField, validators
from wtforms.fields import SelectField, DateField, HiddenField
from flask_admin.model.form import InlineFormAdmin
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from decimal import Decimal
from datetime import datetime
from jinja2 import Template
# filterequal
from flask_admin.contrib.sqla.filters import FilterEqual

from models import (
    db,
    Product,
    Transaction,
    TransactionItem,
    Ledger,
    JurnalUmum,
    NeracaSaldoAwal,
    NeracaSaldo,
    get_last_saldo,
    LedgerMerged
)

# --- Flask Setup ---
app = Flask(__name__)
app.config['SECRET_KEY']               = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI']  = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# --- Helper for LedgerMerged filter ---
def get_account_name_choices():
    names1 = db.session.query(NeracaSaldoAwal.account_name).distinct().all()
    names2 = db.session.query(Ledger.account_name).distinct().all()
    unique = sorted({n[0] for n in names1 + names2 if n[0]})
    return [(n, n) for n in unique]


# --- Auth Forms & Views ---
class LoginForm(Form):
    username = StringField('Username', [validators.InputRequired()])
    password = PasswordField('Password', [validators.InputRequired()])

class MyAdminHome(AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')

class LoginView(BaseView):
    @expose('/', methods=('GET','POST'))
    def index(self):
        form = LoginForm(request.form)
        if request.method=='POST' and form.validate():
            if form.username.data=='admin' and form.password.data=='password':
                session['logged_in']=True
                flash('Login berhasil!','success')
                return redirect('/landing')
            flash('Username atau password salah.','error')
        return self.render('admin/model/edit.html', form=form)

class LogoutView(BaseView):
    @expose('/')
    def index(self):
        session.pop('logged_in', None)
        flash('Logout berhasil.','info')
        return redirect(url_for('login.index'))

class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('logged_in', False)
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login.index'))


# --- Transaction (Sales) ---
class TransactionItemInline(InlineFormAdmin):
    form_overrides = {'id': HiddenField}
    form_columns   = ['id','product','quantity']

class TransactionView(SecureModelView):
    inline_models = [TransactionItemInline(TransactionItem)]
    form_columns   = ['date','items']

    def on_model_change(self, form, model, is_created):
        # only compute totals & adjust stock here
        if is_created:
            total = Decimal('0.00')
            with db.session.no_autoflush:
                for item in model.items:
                    prod = item.product
                    if prod.stock < item.quantity:
                        raise ValueError(f"Stok '{prod.name}' tidak cukup.")
                    prod.stock    -= item.quantity
                    item.subtotal  = prod.price * item.quantity
                    total         += item.subtotal
            model.total = total


    def create_model(self, form):
        model = super().create_model(form)
        total = sum(i.subtotal for i in model.items)
        now   = model.date or datetime.utcnow()
        saldo0 = Decimal(get_last_saldo())

        # Debit Kas Tunai
        db.session.add(Ledger(
            tanggal=now,
            keterangan=f"Penjualan Transaksi #{model.id}",
            account_name="Kas Tunai",
            debit=total, kredit=Decimal('0.00'),
            saldo=saldo0 + total
        ))
        # Credit Penjualan
        db.session.add(Ledger(
            tanggal=now,
            keterangan=f"Penjualan Transaksi #{model.id}",
            account_name="Penjualan",
            debit=Decimal('0.00'), kredit=total,
            saldo=saldo0
        ))
        db.session.commit()
        return model





# --- Product Purchase (Inventory) ---
class ProductView(SecureModelView):
    form_columns = ['name','price','stock','satuan','transaction_account']
    form_extra_fields = {
        'transaction_account': SelectField(
            'Akun Lawan',
            choices=[
                ('Kas Tunai','Kas Tunai'),
                ('Utang Usaha','Utang Usaha'),
                ('Persediaan Barang','Persediaan Barang'),
            ],
            validators=[validators.InputRequired()]
        )
    }

    def on_model_change(self, form, model, is_created):
        if not is_created:
            return super().on_model_change(form, model, is_created)

        try:
            cost   = model.price * Decimal(model.stock)
            now    = datetime.utcnow()
            saldo0 = Decimal(get_last_saldo() or 0)

            # 1) Debit Inventory
            db.session.add(Ledger(
                tanggal=now,
                keterangan=f"Pembelian {model.name}",
                account_name="Persediaan Barang",
                debit=cost,
                kredit=Decimal('0.00'),
                saldo=saldo0 + cost
            ))
            # 2) Credit Cash/Payable
            db.session.add(Ledger(
                tanggal=now,
                keterangan=f"Pembelian {model.name}",
                account_name=form.transaction_account.data,
                debit=Decimal('0.00'),
                kredit=cost,
                saldo=saldo0
            ))

            super().on_model_change(form, model, is_created)

        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash(f"Gagal menyimpan Product: {e}", 'error')
            raise






# --- Opening Balance ---
class NeracaSaldoAwalView(SecureModelView):
    form_columns = ['tanggal','account_name','debit','kredit']
    form_overrides = {'tanggal': DateField}
    form_args      = {'tanggal': {'widget': DatePickerWidget()}}
    form_extra_fields = {
        'account_name': SelectField(
            'Akun',
            choices=[
                ('Kas Tunai','Kas Tunai'),
                ('Persediaan Barang','Persediaan Barang'),
                ('Modal Awal','Modal Awal'),
                ('Utang Usaha','Utang Usaha'),
            ],
            validators=[validators.InputRequired()]
        )
    }

    def on_model_change(self, form, model, is_created):
        if not is_created:
            return super().on_model_change(form, model, is_created)

        try:
            amt    = (model.debit or Decimal('0.00')) - (model.kredit or Decimal('0.00'))
            now    = model.tanggal
            saldo0 = Decimal(get_last_saldo() or 0)

            # 1) Debit Account
            if model.debit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Saldo Awal {model.account_name}",
                    account_name=model.account_name,
                    debit=model.debit,
                    kredit=Decimal('0.00'),
                    saldo=saldo0 + amt
                ))
            # 2) Credit Opening Equity
            if model.kredit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Saldo Awal {model.account_name}",
                    account_name="Modal Awal",
                    debit=Decimal('0.00'),
                    kredit=model.kredit,
                    saldo=saldo0
                ))

            super().on_model_change(form, model, is_created)

        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash(f"Gagal menyimpan Neraca Saldo Awal: {e}", 'error')
            raise

# --- Ongoing Balance Update ---
class NeracaSaldoView(SecureModelView):
    form_columns = ['akun','debit','kredit']
    form_extra_fields = {
        'akun': SelectField(
            'Akun',
            choices=[
                ('Kas Tunai','Kas Tunai'),
                ('Persediaan Barang','Persediaan Barang'),
                ('Penjualan','Penjualan'),
                ('Utang Usaha','Utang Usaha'),
            ],
            validators=[validators.InputRequired()]
        )
    }

    def on_model_change(self, form, model, is_created):
        if not is_created:
            return super().on_model_change(form, model, is_created)

        try:
            change  = (model.debit or Decimal('0.00')) - (model.kredit or Decimal('0.00'))
            now     = datetime.utcnow()
            saldo0  = Decimal(get_last_saldo() or 0)

            # 1) Debit Account
            if model.debit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Neraca Saldo: {model.akun}",
                    account_name=model.akun,
                    debit=model.debit,
                    kredit=Decimal('0.00'),
                    saldo=saldo0 + change
                ))
            # 2) Credit Adjustment Equity
            if model.kredit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Neraca Saldo: {model.akun}",
                    account_name="Saldo Penyesuaian",
                    debit=Decimal('0.00'),
                    kredit=model.kredit,
                    saldo=saldo0
                ))

            super().on_model_change(form, model, is_created)

        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash(f"Gagal menyimpan Neraca Saldo: {e}", 'error')
            raise






# --- General Journal ---
class JurnalUmumView(SecureModelView):
    form_columns    = ['tanggal','transaksi','debit','kredit']
    form_extra_fields = {
        'tanggal': DateField('Tanggal', widget=DatePickerWidget()),
        'transaksi': SelectField(
            'Akun/Transaksi',
            choices=[
                ('Biaya Perlengkapan','Biaya Perlengkapan'),
                ('Pendapatan Lain','Pendapatan Lain'),
                ('Utang Usaha','Utang Usaha'),
            ],
            validators=[validators.InputRequired()]
        )
    }

    def on_model_change(self, form, model, is_created):
        if not is_created:
            return super().on_model_change(form, model, is_created)

        try:
            amt     = (model.debit or Decimal('0.00')) - (model.kredit or Decimal('0.00'))
            now     = model.tanggal
            saldo0  = Decimal(get_last_saldo() or 0)

            # 1) Debit if any
            if model.debit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Jurnal: {model.transaksi}",
                    account_name=model.transaksi,
                    debit=model.debit,
                    kredit=Decimal('0.00'),
                    saldo=saldo0 + model.debit
                ))
            # 2) Credit if any
            if model.kredit:
                db.session.add(Ledger(
                    tanggal=now,
                    keterangan=f"Jurnal: {model.transaksi}",
                    account_name="Kas Tunai",
                    debit=Decimal('0.00'),
                    kredit=model.kredit,
                    saldo=saldo0
                ))

            super().on_model_change(form, model, is_created)

        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash(f"Gagal menyimpan Jurnal Umum: {e}", 'error')
            raise






# --- Read-Only Unified Ledger View ---
class LedgerView(SecureModelView):
    can_create  = can_edit = can_delete = False

    column_list         = ['tanggal','account_name','keterangan','debit','kredit','saldo']
    column_default_sort = ('tanggal', True)

    # Hard-coded dropdown choices
    ACCOUNT_CHOICES = [
        ('Kas Tunai', 'Kas Tunai'),
        ('Penjualan', 'Penjualan'),
        ('Persediaan Barang', 'Persediaan Barang'),
        ('Utang Usaha', 'Utang Usaha'),
        ('Modal Awal', 'Modal Awal'),
        ('Saldo Penyesuaian', 'Saldo Penyesuaian'),
        # add any other accounts here…
    ]

    column_filters = [
        FilterEqual(
            column=Ledger.account_name,
            name='Account Name',
            options=ACCOUNT_CHOICES
        )
    ]




# --- Admin setup ---
admin = Admin(app, name='SIM Admin', index_view=MyAdminHome(), template_mode='bootstrap4')
admin.add_view(LoginView(name='Login',    endpoint='login'))
admin.add_view(LogoutView(name='Logout', endpoint='logout'))
admin.add_view(ProductView(Product, db.session, name='Product',          endpoint='product'))
admin.add_view(TransactionView(Transaction, db.session, name='Transaksi', endpoint='transaksi'))
admin.add_view(JurnalUmumView(JurnalUmum, db.session, name='Jurnal',      endpoint='jurnalumum'))
admin.add_view(NeracaSaldoAwalView(NeracaSaldoAwal, db.session,
                                   name='Saldo Awal', endpoint='neraca_awal'))
admin.add_view(NeracaSaldoView(NeracaSaldo, db.session,
                               name='Saldo Berjalan', endpoint='neracasaldo'))

ledger_view = LedgerView(Ledger, db.session, name='Ledger', endpoint='ledger')
admin.add_view(ledger_view)

# --- Public Landing Page at / ---
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


@app.errorhandler(500)
def internal_error(err):
    return str(err), 500

if __name__ == '__main__':
    with app.app_context():
        # 1) Create tables
        db.create_all()

        # 2) (Re)create the ledger_merged VIEW
        # db.session.execute(text("DROP VIEW IF EXISTS ledger_merged;"))
        # db.session.execute(text("""
        # CREATE VIEW ledger_merged AS
        #   SELECT
        #     ROW_NUMBER() OVER (ORDER BY tanggal) AS id,
        #     tanggal,
        #     account_name,
        #     'Saldo Awal'    AS keterangan,
        #     debit, kredit,
        #     debit - kredit  AS saldo,
        #     'Opening'        AS sumber
        #   FROM neraca_saldo_awal

        #   UNION ALL

        #   SELECT
        #     ROW_NUMBER() OVER (ORDER BY tanggal) +
        #       (SELECT COUNT(*) FROM neraca_saldo_awal) AS id,
        #     date(tanggal) AS tanggal,
        #     account_name,
        #     keterangan,
        #     debit, kredit,
        #     saldo,
        #     'Ledger' AS sumber
        #   FROM ledger_entries
        # """))
        db.session.commit()

        # 3) Now that tables & VIEW exist, populate the filter choices
        ledger_view.column_choices = {
            'account_name': get_account_name_choices()
        }

    app.run(debug=True, host='0.0.0.0')
