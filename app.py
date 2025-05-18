from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView  # ✅ Tambahkan baris ini
from datetime import datetime
from sqlalchemy.orm import Session

from models import (
    db, Product, Transaction, TransactionItem,
    Ledger, JurnalUmum, NeracaSaldoAwal, NeracaSaldo,
    TransactionView
)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret123'

db.init_app(app)

admin = Admin(app, name='SIM Admin', template_mode='bootstrap4')
admin.add_view(ModelView(Product, db.session))
admin.add_view(TransactionView(Transaction, db.session))
admin.add_view(ModelView(Ledger, db.session))
admin.add_view(ModelView(JurnalUmum, db.session))
admin.add_view(ModelView(NeracaSaldoAwal, db.session))
admin.add_view(ModelView(NeracaSaldo, db.session))

@app.route('/')
def index():
    return render_template("landing.html")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)




