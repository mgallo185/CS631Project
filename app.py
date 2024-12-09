from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Dragonba!!1227@localhost/WALLET_APP'  # Replace with your credentials
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable modification tracking for performance
app.secret_key = 'your_secret_key'  # Ensure you add a secret key for session management

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # The name of the login view

# User model
class User(UserMixin, db.Model):
    SSN = db.Column(db.String(9), primary_key=True)
    first_name = db.Column(db.String(50))
    middle_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    isVerified = db.Column(db.Boolean)
    password = db.Column(db.String(255))

    def get_id(self):
        return str(self.SSN)

# Email model
class Email(db.Model):
    email_address = db.Column(db.String(255), primary_key=True)
    ssn = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    isVerified = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='emails')

# Wallet Account model
class WalletAccount(db.Model):
    wallet_id = db.Column(db.Integer, primary_key=True)
    SSN = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    balance = db.Column(db.Numeric(10, 2))
    isVerified = db.Column(db.Boolean)
    PIN = db.Column(db.String(4))

    user = db.relationship('User', backref='wallet_accounts')

# Bank Account model
class BankAccount(db.Model):
    bank_id = db.Column(db.Integer, nullable=False)  # Part of the composite primary key
    account_number = db.Column(db.String(100), nullable=False)
    ssn = db.Column(db.String(9), db.ForeignKey('user.SSN'), nullable=False)  # Match length to User SSN
    balance = db.Column(db.Float, default=0.0)
    isVerified = db.Column(db.Boolean, default=False)
    expiration_date = db.Column(db.Date, nullable=True)

    # Composite primary key
    __table_args__ = (
        db.PrimaryKeyConstraint('bank_id', 'account_number', 'ssn'),
    )

    # Define the relationship to User
    user = db.relationship('User', backref='bank_accounts')
# Transfer History model
class TransferHistory(db.Model):
    transfer_id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank_account.bank_id'))
    account_number = db.Column(db.String(20))
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet_account.wallet_id'))
    SSN = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    amount = db.Column(db.Numeric(10, 2))
    wallet_to_bank = db.Column(db.Boolean)
    Time_Initiated = db.Column(db.DateTime)
    Time_Completed = db.Column(db.DateTime)
    status = db.Column(db.String(20))

    bank_account = db.relationship('BankAccount', backref='transfer_histories')
    wallet_account = db.relationship('WalletAccount', backref='transfer_histories')
    user = db.relationship('User', backref='transfer_histories')

# Monthly Statement model
class MonthlyStatement(db.Model):
    monthly_statement_id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet_account.wallet_id'))
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.transaction_id'))
    For_Month_Year = db.Column(db.Date)
    starting_balance = db.Column(db.Numeric(10, 2))
    total_amount_sent = db.Column(db.Numeric(10, 2))
    total_amount_received = db.Column(db.Numeric(10, 2))
    net_change = db.Column(db.Numeric(10, 2))
    ending_balance = db.Column(db.Numeric(10, 2))

    wallet_account = db.relationship('WalletAccount', backref='monthly_statements')
    transaction = db.relationship('Transaction', backref='monthly_statements')

# Transaction model
class Transaction(db.Model):
    transaction_id = db.Column(db.Integer, primary_key=True)
    sender_wallet_id_ssn = db.Column(db.String(9), db.ForeignKey('wallet_account.SSN'))
    receiver_wallet_id_ssn = db.Column(db.String(9), db.ForeignKey('wallet_account.SSN'))
    initiation_timestamp = db.Column(db.DateTime)
    completion_timestamp = db.Column(db.DateTime)
    amount = db.Column(db.Numeric(10, 2))
    memo = db.Column(db.Text)
    status = db.Column(db.String(20))

    sender_wallet = db.relationship('WalletAccount', foreign_keys=[sender_wallet_id_ssn], backref='sent_transactions')
    receiver_wallet = db.relationship('WalletAccount', foreign_keys=[receiver_wallet_id_ssn], backref='received_transactions')

# Send Money model
class SendMoney(db.Model):
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.transaction_id'), primary_key=True)
    recipient_phone_email = db.Column(db.String(255))
    cancellation_reason = db.Column(db.Text)
    cancellation_timestamp = db.Column(db.DateTime)

    transaction = db.relationship('Transaction', backref='send_money')

# Request Money model
class RequestMoney(db.Model):
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.transaction_id'), primary_key=True)
    request_id = db.Column(db.Integer)
    requestees_phone_email = db.Column(db.String(255))
    expiration_date = db.Column(db.Date)
    isNewUser = db.Column(db.Boolean)

    transaction = db.relationship('Transaction', backref='request_money')

# Ensure tables are created if they don't exist
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        ssn = request.form['ssn']
        first_name = request.form['first_name']
        middle_name = request.form['middle_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        email_address = request.form['email']  # Get the email from the form
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')

        # Check if user already exists
        existing_user = User.query.filter_by(SSN=ssn).first()
        if existing_user:
            flash("User already exists with that SSN!", "danger")
            return redirect(url_for('register'))

        # Check if email already exists
        existing_email = Email.query.filter_by(email_address=email_address).first()
        if existing_email:
            flash("Email is already associated with another account!", "danger")
            return redirect(url_for('register'))

        # Create a new user
        new_user = User(
            SSN=ssn, 
            first_name=first_name, 
            middle_name=middle_name, 
            last_name=last_name, 
            phone=phone, 
            password=password, 
            isVerified=False
        )

        # Create a new email entry
        new_email = Email(email_address=email_address, ssn=ssn, isVerified=False)

        # Add the user and email to the database
        db.session.add(new_user)
        db.session.add(new_email)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']  # This can be SSN or email
        password = request.form['password']

        # Check if the identifier matches an SSN
        user = User.query.filter_by(SSN=identifier).first()
        if not user:
            # If not SSN, check if it matches an email
            email_entry = Email.query.filter_by(email_address=identifier).first()
            if email_entry:
                user = User.query.filter_by(SSN=email_entry.ssn).first()

        # If user is found and password matches
        if user and check_password_hash(user.password, password):
            login_user(user)  # This logs in the user via Flask-Login
            session['SSN'] = user.SSN  # Store SSN in the session
            flash("Login successful!", "success")
            return redirect(url_for('index'))  # Redirect to homepage or dashboard
        
        flash("Invalid login credentials. Please try again.", "danger")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update user information
        user = User.query.get(current_user.get_id())

        user.first_name = request.form['first_name']
        user.middle_name = request.form['middle_name']
        user.last_name = request.form['last_name']
        user.phone = request.form['phone']
        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))

    return render_template('profile.html')

@app.route('/add_bank_account', methods=['GET', 'POST'])
def add_bank_account():
    if request.method == 'POST':
        bank_id = request.form['bank_id']
        account_number = request.form['account_number']
        PIN = request.form['PIN']
        balance = request.form['balance']
        expiration_date = request.form['expiration_date']
        ssn = request.form['SSN']  # SSN comes from the hidden field

        # Create a new bank account using the form data
        new_account = BankAccount(
            bank_id=bank_id,
            account_number=account_number,
            ssn=ssn,
            balance=balance,
            expiration_date=expiration_date,
            isVerified=False  # Assuming the account isn't verified right away
        )

        db.session.add(new_account)
        db.session.commit()

        flash('Bank account added successfully!', 'success')
        return redirect(url_for('index'))  # Redirect to dashboard or another page after success
    return render_template('add_bank_account.html')
if __name__ == '__main__':
    app.run(debug=True)
