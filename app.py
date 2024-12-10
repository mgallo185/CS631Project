from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime




app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://songjiang:123456@34.42.219.23:3306/wallet'  # Replace with your credentials
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
    
    emails = db.relationship('Email', backref='user')
    def get_id(self):
        return str(self.SSN)

# Email model
class Email(db.Model):
    email_address = db.Column(db.String(255), primary_key=True)
    ssn = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    isVerified = db.Column(db.Boolean, default=False)



# Wallet Account model
class WalletAccount(db.Model):
    wallet_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SSN = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    balance = db.Column(db.Numeric(10, 2))
    isVerified = db.Column(db.Boolean)
    PIN = db.Column(db.String(4))

    user = db.relationship('User', backref='wallet_accounts')

    @property
    def wallet_id_formatted(self):
        # Return a 10-digit wallet ID with leading zeros
        return f'{self.wallet_id:010d}'


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
    wallet_balance = None  # Default to None if the user is not logged in
    wallet_account = None  # Default to None if the user is not logged in

    if current_user.is_authenticated:
        # Fetch the wallet account for the logged-in user
        wallet_account = WalletAccount.query.filter_by(SSN=current_user.SSN).first()
        wallet_balance = wallet_account.balance if wallet_account else 0.00  # Default to 0.00 if no wallet exists

    return render_template('index.html', wallet_balance=wallet_balance, wallet_account=wallet_account)

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
        
        # Create a new wallet account for the user
        new_wallet = WalletAccount(
            SSN=ssn,
            balance=0.00,  # Default balance is 0
            isVerified=False,  # Default to not verified
        )

        # Add the user, email, and wallet to the database
        db.session.add(new_user)
        db.session.add(new_email)
        db.session.add(new_wallet)
        db.session.commit()

        flash(f"Registration successful! Your wallet ID is {new_wallet.wallet_id_formatted}. Please log in.", "success")
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

@app.route('/add_email', methods=['POST'])
@login_required
def add_email():
    user = User.query.get(current_user.get_id())
    email_address = request.form['email']
    
    # Check if email already exists
    existing_email = Email.query.filter_by(email_address=email_address).first()
    if existing_email:
        flash("Email is already associated with another account!", "danger")
        return redirect(url_for('profile'))

    # Create new email entry
    new_email = Email(email_address=email_address, ssn=user.SSN, isVerified=False)

    # Add the email to the user's email list
    db.session.add(new_email)
    db.session.commit()

    flash('Email added successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/remove_email/<email>', methods=['GET'])
@login_required
def remove_email(email):
    # Clean and preprocess the email string
    email = email.strip().lower()
    if email.startswith('<email '):  # Remove '<email ' prefix if present
        email = email.replace('<email ', '').rstrip('>')  # Remove '>'

    print("Email to remove:", email)

    # Extract the actual email addresses from the user's emails
    user_emails = [e.email_address.strip().lower() for e in current_user.emails]
    print("Current user's emails:", user_emails)

    # Check if the email exists in the user's email list
    if email in user_emails:
        # Retrieve the corresponding Email object to delete
        email_obj = next((e for e in current_user.emails if e.email_address.strip().lower() == email), None)
        if email_obj:
            db.session.delete(email_obj)  # Remove from the database
            db.session.commit()  # Commit the changes
            flash('Email removed successfully!', 'success')
        else:
            flash('Email object not found.', 'danger')
    else:
        flash('Email not found.', 'danger')
    
    return redirect(url_for('profile'))



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

@app.route('/remove_bank_account', methods=['POST'])
@login_required
def remove_bank_account():
    # Retrieve the composite primary key values from the form
    bank_id = request.form['bank_id']
    account_number = request.form['account_number']
    ssn = current_user.SSN  # Assuming the SSN is associated with the logged-in user

    # Find the bank account with the composite primary key
    account_to_remove = BankAccount.query.get((bank_id, account_number, ssn))

    if account_to_remove:
        # Delete the account from the database
        db.session.delete(account_to_remove)
        db.session.commit()
        flash('Bank account removed successfully!', 'success')
    else:
        flash('Bank account not found.', 'danger')

    return redirect(url_for('profile'))

@app.route('/send_money', methods=['GET', 'POST'])
@login_required
def send_money():
    if request.method == 'POST':
        recipient_identifier = request.form['recipient']  # Can be email, phone, or wallet ID
        amount = float(request.form['amount'])
        sender_wallet = WalletAccount.query.filter_by(SSN=current_user.SSN).first()

        if not sender_wallet:
            flash("Sender wallet not found.", "danger")
            return redirect(url_for('send_money'))

        if sender_wallet.balance < amount:
            flash("Insufficient balance to complete the transaction.", "danger")
            return redirect(url_for('send_money'))

        # Find recipient
        recipient_user = None
        if '@' in recipient_identifier:  # Check if it's an email
            email_entry = Email.query.filter_by(email_address=recipient_identifier).first()
            if email_entry:
                recipient_user = User.query.filter_by(SSN=email_entry.ssn).first()
        elif recipient_identifier.isdigit():  # Assume phone number
            recipient_user = User.query.filter_by(phone=recipient_identifier).first()
        else:  # Assume wallet ID
            recipient_wallet = WalletAccount.query.filter_by(wallet_id=recipient_identifier).first()
            if recipient_wallet:
                recipient_user = User.query.filter_by(SSN=recipient_wallet.SSN).first()

        if not recipient_user:
            flash("Recipient not found.", "danger")
            return redirect(url_for('send_money'))

        # Get recipient wallet
        recipient_wallet = WalletAccount.query.filter_by(SSN=recipient_user.SSN).first()

        # Perform transfer
        sender_wallet.balance -= amount
        recipient_wallet.balance += amount

        # Log transaction
        transaction = Transaction(
            sender_wallet_id_ssn=sender_wallet.SSN,
            receiver_wallet_id_ssn=recipient_wallet.SSN,
            initiation_timestamp=datetime.now(),
            amount=amount,
            memo=request.form.get('memo', ''),
            status="Completed"
        )
        db.session.add(transaction)
        db.session.commit()

        flash(f"Sent ${amount} to {recipient_identifier} successfully!", "success")
        return redirect(url_for('dashboard'))  # Redirect to dashboard or another relevant page

    return render_template('send_money.html')



@app.route('/request_money', methods=['GET', 'POST'])
@login_required
def request_money():
    if request.method == 'POST':
        recipients = request.form.getlist('recipients')  # List of recipient emails/phone numbers
        amounts = request.form.getlist('amounts')  # List of corresponding amounts
        memo = request.form.get('memo', '')  # Optional memo
        expiration_date = request.form.get('expiration_date', None)  # Optional expiration date
        
        if not recipients or not amounts or len(recipients) != len(amounts):
            flash("Invalid request data. Ensure recipients and amounts match.", "danger")
            return redirect(url_for('request_money'))
        
        # Process each recipient
        for i, recipient in enumerate(recipients):
            amount = float(amounts[i])
            is_new_user = not User.query.filter(
                (User.SSN == recipient) | 
                (Email.email_address == recipient) | 
                (User.phone == recipient)
            ).first()
            
            # Create a transaction
            transaction = Transaction(
                initiation_timestamp=datetime.now(),
                amount=amount,
                memo=memo,
                status='Pending'
            )
            db.session.add(transaction)
            db.session.commit()  # Commit to generate transaction_id
            
            # Create the money request
            request_money = RequestMoney(
                transaction_id=transaction.transaction_id,
                requestees_phone_email=recipient,
                amount=amount,
                memo=memo,
                expiration_date=expiration_date,
                isNewUser=is_new_user
            )
            db.session.add(request_money)
        
        db.session.commit()
        flash("Money requests sent successfully!", "success")
        return redirect(url_for('dashboard'))  # Replace 'dashboard' with your app's main page
    
    return render_template('request_money.html')


if __name__ == '__main__':
    app.run(debug=True)
