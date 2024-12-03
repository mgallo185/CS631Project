from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Dragonba!!1227@localhost/WALLET_APP'  # Replace with your credentials
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable modification tracking for performance

db = SQLAlchemy(app)

class User(db.Model):
    SSN = db.Column(db.String(9), primary_key=True)
    first_name = db.Column(db.String(50))
    middle_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    isVerified = db.Column(db.Boolean)
    password = db.Column(db.String(255))

    def __repr__(self):
        return f'<User {self.first_name} {self.last_name}>'


@app.route('/')
def index():
    all_users = User.query.all()  # Fetch all users from the database
    return render_template('index.html', users=all_users)

if __name__ == '__main__':
    app.run(debug=True)
