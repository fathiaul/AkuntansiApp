from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.orm import Session
from wtforms.fields import HiddenField
from flask_admin.model.form import InlineFormAdmin

db = SQLAlchemy()

# ========================
# USER LOGIN
# ========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ========================
# PRODUK
# ========================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    satuan = db.Column(db.String(20), nullable=True)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Product {self.name}>"

# ========================
# TRANSAKSI
# ========================
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False, default=0)

    items = db.relationship(
        'TransactionItem',
        back_populates='transaction',
        cascade="all, delete-orphan"
    )

class TransactionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    transaction = db.relationship('Transaction', back_populates='items')
    product = db.relationship('Product')

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

# ========================
# BUKU BESAR (LEDGER)
# ========================
class Ledger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    keterangan = db.Column(db.String(255), nullable=False)
    akun = db.Column(db.String(255), nullable=False)  # ✅ Kolom akun ditambahkan
    debit = db.Column(db.Float, default=0)
    kredit = db.Column(db.Float, default=0)
    saldo = db.Column(db.Float, default=0)

# ========================
# JURNAL UMUM
# ========================
class JurnalUmum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaksi = db.Column(db.String(255), nullable=False)
    debit = db.Column(db.Float, default=0)
    kredit = db.Column(db.Float, default=0)

    def __repr__(self):
        return f"<Jurnal {self.transaksi}>"

# ========================
# NERACA SALDO AWAL
# ========================
class NeracaSaldoAwal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    akun = db.Column(db.String(255), nullable=False)
    debit = db.Column(db.Float, default=0)
    kredit = db.Column(db.Float, default=0)

    def __repr__(self):
        return f"<NeracaSaldoAwal {self.akun}>"

# ========================
# NERACA SALDO BERJALAN
# ========================
class NeracaSaldo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    akun = db.Column(db.String(255), nullable=False)
    debit = db.Column(db.Float, default=0)
    kredit = db.Column(db.Float, default=0)

    def __repr__(self):
        return f"<NeracaSaldo {self.akun}>"

# ========================
# FUNGSI BANTU
# ========================
def get_last_saldo():
    last_entry = Ledger.query.order_by(Ledger.id.desc()).first()
    return last_entry.saldo if last_entry else 0

# ========================
# INLINE MODEL UNTUK TRANSACTION ITEM
# ========================
class TransactionItemInlineModel(InlineFormAdmin):
    form_overrides = dict(id=HiddenField)
    form_columns = ['id', 'product', 'quantity']

# ========================
# ADMIN VIEW TRANSAKSI
# ========================
class TransactionView(ModelView):
    inline_models = [TransactionItemInlineModel(TransactionItem)]
    form_columns = ['date', 'items']

    def on_model_change(self, form, model, is_created):
        total = 0
        session: Session = db.session

        with session.no_autoflush:
            for item in model.items:
                product = item.product
                if not product:
                    raise ValueError("Produk tidak ditemukan.")
                if product.stock < item.quantity:
                    raise ValueError(f"Stok produk '{product.name}' tidak cukup.")
                product.stock -= item.quantity
                item.subtotal = item.quantity * product.price
                total += item.subtotal

        model.total = total

        # Catat ke Ledger
        saldo_sebelumnya = get_last_saldo()
        keterangan = f"Penjualan Transaksi ID: {model.id}"
        akun = "Penjualan"  # Akun wajib untuk Ledger
        session.add(Ledger(
            tanggal=model.date,
            keterangan=keterangan,
            akun=akun,  # ✅ disertakan untuk hindari NOT NULL error
            debit=total,
            kredit=0,
            saldo=saldo_sebelumnya + total
        ))

        # Catat ke Jurnal Umum
        session.add(JurnalUmum(
            tanggal=model.date,
            transaksi=keterangan,
            debit=total,
            kredit=0
        ))

        # Catat ke Neraca Saldo Awal
        session.add(NeracaSaldoAwal(
            tanggal=model.date,
            akun=akun,
            debit=total,
            kredit=0
        ))

        # Catat ke Neraca Saldo Berjalan
        session.add(NeracaSaldo(
            akun=akun,
            debit=total,
            kredit=0
        ))

        super().on_model_change(form, model, is_created)




