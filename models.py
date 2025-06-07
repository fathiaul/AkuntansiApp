# models.py

from sqlalchemy import func
from sqlalchemy.orm import relationship
from sqlalchemy import func, Column, Integer, String, Date, DateTime, Numeric, ForeignKey
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id            = Column(Integer, primary_key=True)
    username      = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)

    def set_password(self, pwd):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, pwd)

    def __repr__(self):
        return f"<User {self.username}>"


class Product(db.Model):
    __tablename__ = 'products'

    id     = Column(Integer, primary_key=True)
    name   = Column(String(100), nullable=False)
    price  = Column(Numeric(18, 2), nullable=False)    # use fixed‐point
    stock  = Column(Integer, default=0, nullable=False)
    satuan = Column(String(20))

    def __repr__(self):
        return f"<Product {self.name} | {self.stock} {self.satuan} @ {self.price}>"


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id    = Column(Integer, primary_key=True)
    date  = Column(DateTime, nullable=False, default=datetime.utcnow,
                   server_default=func.now())
    total = Column(Numeric(18, 2), nullable=False, default=0)

    items = relationship(
        'TransactionItem',
        back_populates='transaction',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Transaction {self.id} @ {self.date:%Y-%m-%d} | Total={self.total}>"


class TransactionItem(db.Model):
    __tablename__ = 'transaction_items'

    id             = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'), nullable=False)
    product_id     = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity       = Column(Integer, nullable=False)
    subtotal       = Column(Numeric(18, 2), nullable=False)

    transaction = relationship('Transaction', back_populates='items')
    product     = relationship('Product')

    def __repr__(self):
        return f"<Item {self.product.name} x{self.quantity} = {self.subtotal}>"


class Ledger(db.Model):
    __tablename__ = 'ledger_entries'

    id           = Column(Integer, primary_key=True)
    tanggal      = Column(DateTime, nullable=False, default=datetime.utcnow,
                          server_default=func.now())
    keterangan   = Column(String(255), nullable=False)
    account_name = Column(String(100), nullable=False)
    debit        = Column(Numeric(18, 2), default=0, nullable=False)
    kredit       = Column(Numeric(18, 2), default=0, nullable=False)
    saldo        = Column(Numeric(18, 2), default=0, nullable=False)

    def __repr__(self):
        return (f"<Ledger {self.tanggal:%Y-%m-%d %H:%M} | "
                f"{self.account_name} D:{self.debit} K:{self.kredit} S:{self.saldo}>")


class JurnalUmum(db.Model):
    __tablename__ = 'jurnal_umum'

    id        = Column(Integer, primary_key=True)
    tanggal   = Column(DateTime, nullable=False, default=datetime.utcnow,
                       server_default=func.now())
    transaksi = Column(String(255), nullable=False)
    debit     = Column(Numeric(18, 2), default=0, nullable=False)
    kredit    = Column(Numeric(18, 2), default=0, nullable=False)

    def __repr__(self):
        return f"<Jurnal {self.transaksi} @ {self.tanggal:%Y-%m-%d}>"


class NeracaSaldoAwal(db.Model):
    __tablename__ = 'neraca_saldo_awal'

    id           = Column(Integer, primary_key=True)
    tanggal      = Column(Date, nullable=False, default=datetime.utcnow().date,
                          server_default=func.current_date())
    account_name = Column(String(100), nullable=False)
    debit        = Column(Numeric(18, 2), default=0, nullable=False)
    kredit       = Column(Numeric(18, 2), default=0, nullable=False)

    def __repr__(self):
        return (f"<SaldoAwal {self.account_name} | "
                f"D:{self.debit} K:{self.kredit} @ {self.tanggal}>")


class NeracaSaldo(db.Model):
    __tablename__ = 'neraca_saldo'

    id     = Column(Integer, primary_key=True)
    akun   = Column(String(255), nullable=False)
    debit  = Column(Numeric(18, 2), default=0, nullable=False)
    kredit = Column(Numeric(18, 2), default=0, nullable=False)

    def __repr__(self):
        return f"<NeracaSaldo {self.akun} D:{self.debit} K:{self.kredit}>"


# ------------------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------------------

def get_last_saldo():
    last = db.session.query(Ledger).order_by(Ledger.id.desc()).first()
    return float(last.saldo) if last else 0.0

class LedgerMerged(db.Model):
    __tablename__  = 'ledger_merged'
    # these columns must match exactly your VIEW definition below!
    id            = Column(Integer, primary_key=True)
    tanggal       = Column(Date, nullable=False)
    account_name  = Column(String(100), nullable=False)
    keterangan    = Column(String(255), nullable=False)
    debit         = Column(Numeric(18,2), nullable=False)
    kredit        = Column(Numeric(18,2), nullable=False)
    saldo         = Column(Numeric(18,2), nullable=False)
    sumber        = Column(String(50), nullable=False)

    def __repr__(self):
        return f"<LedgerMerged {self.tanggal} {self.account_name} D:{self.debit} K:{self.kredit} S:{self.saldo}>"



