from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask import jsonify
from decimal import Decimal
from sqlalchemy import func


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+mysqldb://mike:5XK#BCSxZ\'(6Do5L@34.42.219.23:3306/wallet'
    '?ssl_ca=cert/server-ca.pem&ssl_cert=cert/client-cert.pem&ssl_key=cert/client-key.pem'
)
# Replace with your credentials
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
    transaction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_wallet_id_ssn = db.Column(db.String(9), db.ForeignKey('wallet_account.SSN'))
    receiver_wallet_id_ssn = db.Column(db.String(9), db.ForeignKey('wallet_account.SSN'))
    initiation_timestamp = db.Column(db.DateTime)
    completion_timestamp = db.Column(db.DateTime)
    amount = db.Column(db.Numeric(10, 2))
    memo = db.Column(db.Text)
    status = db.Column(db.String(50))

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
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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
    transactions = []  # Default empty list for transactions

    if current_user.is_authenticated:
        # Fetch the wallet account for the logged-in user
        wallet_account = WalletAccount.query.filter_by(SSN=current_user.SSN).first()
        wallet_balance = wallet_account.balance if wallet_account else 0.00  # Default to 0.00 if no wallet exists

        # Fetch transactions sent by the logged-in user
        # Fetch the 3 most recent transactions for the current user
        transactions = Transaction.query.filter_by(sender_wallet_id_ssn=current_user.SSN).order_by(Transaction.initiation_timestamp.desc()).limit(3).all()


        # Calculate time difference for cancellation eligibility
        now = datetime.now()
        for transaction in transactions:
            transaction.time_diff = now - transaction.initiation_timestamp
            transaction.can_cancel = transaction.time_diff <= timedelta(minutes=10)  # 10 minutes window

    return render_template('index.html', wallet_balance=wallet_balance, wallet_account=wallet_account, transactions=transactions)


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
        recipient_identifier = request.form['recipient']
        amount = Decimal(request.form['amount'])

        sender_wallet = WalletAccount.query.filter_by(SSN=current_user.SSN).first()

        if not sender_wallet:
            flash("Sender wallet not found.", "danger")
            return redirect(url_for('send_money'))

        if sender_wallet.balance < amount:
            flash("Insufficient balance to complete the transaction.", "danger")
            return redirect(url_for('send_money'))

        recipient_user = None
        if '@' in recipient_identifier:
            email_entry = Email.query.filter_by(email_address=recipient_identifier).first()
            if email_entry:
                recipient_user = User.query.filter_by(SSN=email_entry.ssn).first()
        elif recipient_identifier.isdigit():
            recipient_user = User.query.filter_by(phone=recipient_identifier).first()
        else:
            recipient_wallet = WalletAccount.query.filter_by(wallet_id=recipient_identifier).first()
            if recipient_wallet:
                recipient_user = User.query.filter_by(SSN=recipient_wallet.SSN).first()

        if not recipient_user:
            flash("Recipient not found.", "danger")
            return redirect(url_for('send_money'))

        recipient_wallet = WalletAccount.query.filter_by(SSN=recipient_user.SSN).first()

        sender_wallet.balance -= amount
        recipient_wallet.balance += amount

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

        send_money_record = SendMoney(
            transaction_id=transaction.transaction_id,
            recipient_phone_email=recipient_identifier,
            cancellation_reason=None,
            cancellation_timestamp=None
        )
        db.session.add(send_money_record)
        db.session.commit()

        sender_statement = MonthlyStatement(
            wallet_id=sender_wallet.wallet_id,
            transaction_id=transaction.transaction_id,
            For_Month_Year=datetime.now(),
            starting_balance=sender_wallet.balance + amount,
            total_amount_sent=amount,
            total_amount_received=0,
            net_change=-amount,
            ending_balance=sender_wallet.balance
        )
        db.session.add(sender_statement)

        recipient_statement = MonthlyStatement(
            wallet_id=recipient_wallet.wallet_id,
            transaction_id=transaction.transaction_id,
            For_Month_Year=datetime.now(),
            starting_balance=recipient_wallet.balance - amount,
            total_amount_sent=0,
            total_amount_received=amount,
            net_change=amount,
            ending_balance=recipient_wallet.balance
        )
        db.session.add(recipient_statement)

        try:
            db.session.commit()
            # Update the transaction status to "Completed" and set the completion_timestamp
            #transaction.status = "Completed"
            #transaction.completion_timestamp = datetime.now()  # Set completion timestamp
            #db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing transaction: {str(e)}", "danger")
            return redirect(url_for('send_money'))

        flash(f"Sent ${amount} to {recipient_identifier} successfully!", "success")
        return redirect(url_for('index'))

    return render_template('send_money.html')



@app.route('/request_money', methods=['GET', 'POST'])
@login_required
def request_money():
    if request.method == 'POST':
        recipients = request.form.getlist('recipients[]')  # List of recipient emails/phone numbers
        amounts = request.form.getlist('amounts[]')  # List of corresponding amounts
        memo = request.form.get('memo', '')  # Optional memo
        expiration_date = request.form.get('expiration_date', None)  # Optional expiration date

        if not recipients or not amounts or len(recipients) != len(amounts):
            flash("Invalid request data. Ensure recipients and amounts match.", "danger")
            return redirect(url_for('request_money'))

        total_requested = sum(Decimal(amount) for amount in amounts)  # Ensure total amounts are correct

        # Process each recipient
        for i, recipient in enumerate(recipients):
            amount = Decimal(amounts[i])  # Convert to Decimal for consistency
            is_new_user = not User.query.filter(
                (User.SSN == recipient) | 
                (Email.email_address == recipient) | 
                (User.phone == recipient)
            ).first()  # Check if recipient exists

            # Log recipient identifier and lookup result for debugging
            print(f"Recipient: {recipient}")

            # Look up the recipient user
            recipient_user = None
            if '@' in recipient:  # Check if it's an email
                recipient_user = User.query.join(Email).filter(Email.email_address == recipient).first()
            elif recipient.isdigit():  # Assume phone number
                recipient_user = User.query.filter_by(phone=recipient).first()
            else:  # Assume SSN or wallet ID
                recipient_user = User.query.filter_by(SSN=recipient).first()

            if not recipient_user:
                flash(f"Recipient {recipient} not found.", "danger")
                return redirect(url_for('request_money'))

            # Get recipient wallet using their SSN
            recipient_wallet = WalletAccount.query.filter_by(SSN=recipient_user.SSN).first()

            if not recipient_wallet:
                flash("Recipient wallet not found.", "danger")
                return redirect(url_for('request_money'))

            # Create the transaction (request)
            sender_wallet = WalletAccount.query.filter_by(SSN=current_user.SSN).first()
            if not sender_wallet:
                flash("Sender wallet not found.", "danger")
                return redirect(url_for('request_money'))

            transaction = Transaction(
                sender_wallet_id_ssn=sender_wallet.SSN,
                receiver_wallet_id_ssn=recipient_wallet.SSN,
                initiation_timestamp=datetime.now(),
                amount=amount,
                memo=memo,
                status='Request' 
            )
            db.session.add(transaction)
            db.session.commit()  # Commit to generate transaction_id

            # Create the money request (link to transaction)
            request_money = RequestMoney(
                transaction_id=transaction.transaction_id,
                requestees_phone_email=recipient,
                expiration_date=expiration_date,
                isNewUser=is_new_user
            )
            db.session.add(request_money)

        db.session.commit()
        flash(f"Money requests for ${total_requested} sent successfully!", "success")
        return redirect(url_for('index'))  # Redirect to another page after successful request

    return render_template('request_money.html')


# Verify Bank Account route
@app.route('/verify_bank_account/<int:bank_id>', methods=['POST'])
@login_required
def verify_bank_account(bank_id):
    # Retrieve the bank account
    bank_account = BankAccount.query.filter_by(bank_id=bank_id, ssn=current_user.SSN).first()


    # Check if the bank account exists
    if not bank_account:
        flash('Bank account not found!', 'danger')
        return redirect(url_for('profile'))  # Redirect to profile or any other appropriate page

    # Add $10 to the bank account for verification
    bank_account.balance += 10  # Add $10 to the bank account

    # Mark the bank account as verified
    bank_account.isVerified = True  # Set the verification status to True

    try:
        # Commit changes to the database
        db.session.commit()
        flash('Bank account verified and $10 added!', 'success')
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        flash('An error occurred. Please try again later.', 'danger')

    return redirect(url_for('profile'))


@app.route('/transfer_money_to_wallet', methods=['GET', 'POST'])
@login_required
def transfer_money_to_wallet():
    if request.method == 'POST':
        # Get form data
        wallet_id = request.form.get('wallet_account')  # Wallet ID where money will go
        amount = request.form.get('amount')  # Amount user wants to transfer
        
        # Validate form data
        if not wallet_id or not amount:
            flash('Please provide both wallet account and amount.', 'error')
            return redirect(url_for('transfer_money_to_wallet'))  # Reload the page if form is incomplete

        try:
            # Convert the amount to Decimal for precision
            amount = Decimal(amount)
        except:
            flash('Invalid amount. Please enter a valid number.', 'error')
            return redirect(url_for('transfer_money_to_wallet'))

        # Find the user's bank account
        bank_account = BankAccount.query.filter_by(ssn=current_user.SSN, isVerified=True).first()
        
        if not bank_account:
            flash('No verified bank account found.', 'error')
            return redirect(url_for('transfer_money_to_wallet'))

        # Ensure bank_account.balance is also a Decimal
        bank_balance = Decimal(bank_account.balance)

        # Check if the bank account has enough balance
        if bank_balance < amount:
            flash('Insufficient funds in your bank account.', 'error')
            return redirect(url_for('transfer_money_to_wallet'))

        # Find the wallet account
        wallet_account = WalletAccount.query.filter_by(wallet_id=wallet_id, SSN=current_user.SSN).first()
        
        if not wallet_account:
            flash('Wallet account not found.', 'error')
            return redirect(url_for('transfer_money_to_wallet'))

        # Perform the transfer
        bank_account.balance = str(bank_balance - amount)  # Deduct the amount from the bank account
        wallet_account.balance = str(Decimal(wallet_account.balance) + amount)  # Add the amount to the wallet account

        # Create a TransferHistory record
        transfer = TransferHistory(
            bank_id=bank_account.bank_id,
            account_number=bank_account.account_number,
            wallet_id=wallet_account.wallet_id,
            SSN=current_user.SSN,
            amount=amount,
            wallet_to_bank=False,  # False means money is going to the wallet
            Time_Initiated=datetime.now(),
            status='Completed'  # You could also use 'Pending' here if you need it
        )
        
        # Save everything to the database
        db.session.add(transfer)
        db.session.commit()

        # Success message and redirect
        flash('Transfer completed successfully!', 'success')
        return redirect(url_for('transfer_money_to_wallet'))  # Reload the page after transfer

    # If it's a GET request, render the page with the form
    return render_template('profile.html')


@app.route('/search_transactions', methods=['GET', 'POST'])
@login_required
def search_transactions():
    # Default filters: All transactions for the logged-in user's SSN
    transactions = Transaction.query.filter(
        (Transaction.sender_wallet_id_ssn == current_user.SSN) | 
        (Transaction.receiver_wallet_id_ssn == current_user.SSN)
    )
    
    # Apply additional filters if provided
    if request.method == 'POST':
        transaction_type = request.form.get('transaction_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        amount_min = request.form.get('amount_min')
        amount_max = request.form.get('amount_max')
        search_email_phone = request.form.get('email_phone')  # Email or phone input
        ssn_search = request.form.get('ssn_search')  # SSN search input

        # Filter by transaction type
        if transaction_type:
            if transaction_type == "sent":
                transactions = transactions.filter(Transaction.sender_wallet_id_ssn == current_user.SSN)
            elif transaction_type == "received":
                transactions = transactions.filter(Transaction.receiver_wallet_id_ssn == current_user.SSN)

        # Filter by date range
        if start_date:
            transactions = transactions.filter(Transaction.initiation_timestamp >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            transactions = transactions.filter(Transaction.initiation_timestamp <= datetime.strptime(end_date, '%Y-%m-%d'))

        # Filter by amount range
        if amount_min:
            transactions = transactions.filter(Transaction.amount >= Decimal(amount_min))
        if amount_max:
            transactions = transactions.filter(Transaction.amount <= Decimal(amount_max))

        # Filter by email or phone number
        if search_email_phone:
            transactions = transactions.join(WalletAccount, WalletAccount.SSN == Transaction.sender_wallet_id_ssn)\
                                       .join(User, User.SSN == WalletAccount.SSN)\
                                       .filter(
                                           (User.phone.like(f'%{search_email_phone}%')) | 
                                           (Email.email_address.like(f'%{search_email_phone}%'))
                                       )
        
        # Filter by SSN
        if ssn_search:
            transactions = transactions.filter(
                (Transaction.sender_wallet_id_ssn == ssn_search) | 
                (Transaction.receiver_wallet_id_ssn == ssn_search)
            )

    transactions = transactions.all()  # Execute the query
    return render_template('search_transactions.html', transactions=transactions)
@app.route('/statements', methods=['GET', 'POST'])
@login_required
def statements():
    if request.method == 'POST':
        user_ssn = request.form.get('ssn')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        # Convert date inputs to datetime objects
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        # Query for total and average amount sent/received grouped by month
        sent_by_month_query = db.session.query(
            func.date_format(Transaction.initiation_timestamp, '%Y-%m').label('month'),
            func.sum(Transaction.amount).label('total_sent'),
            func.avg(Transaction.amount).label('avg_sent')
        ).filter(Transaction.sender_wallet_id_ssn == user_ssn)

        received_by_month_query = db.session.query(
            func.date_format(Transaction.initiation_timestamp, '%Y-%m').label('month'),
            func.sum(Transaction.amount).label('total_received'),
            func.avg(Transaction.amount).label('avg_received')
        ).filter(Transaction.receiver_wallet_id_ssn == user_ssn)

        # Apply date filters
        if start_date and end_date:
            sent_by_month_query = sent_by_month_query.filter(
                Transaction.initiation_timestamp.between(start_date, end_date)
            )
            received_by_month_query = received_by_month_query.filter(
                Transaction.initiation_timestamp.between(start_date, end_date)
            )

        # Group by month and execute queries
        sent_by_month = sent_by_month_query.group_by('month').all()
        received_by_month = received_by_month_query.group_by('month').all()

        # Combine results by month for easier display
        combined_results = {}
        for record in sent_by_month:
            month = record[0]
            combined_results[month] = {
                'total_sent': record[1],
                'avg_sent': record[2],
                'total_received': 0,
                'avg_received': 0
            }

        for record in received_by_month:
            month = record[0]
            if month not in combined_results:
                combined_results[month] = {
                    'total_sent': 0,
                    'avg_sent': 0,
                    'total_received': record[1],
                    'avg_received': record[2]
                }
            else:
                combined_results[month]['total_received'] = record[1]
                combined_results[month]['avg_received'] = record[2]

        # Sort results by month
        sorted_results = sorted(combined_results.items(), key=lambda x: x[0])

        # Query for total amount sent and received in the date range
        total_sent = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.sender_wallet_id_ssn == user_ssn,
            Transaction.initiation_timestamp.between(start_date, end_date)
        ).scalar()

        total_received = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.receiver_wallet_id_ssn == user_ssn,
            Transaction.initiation_timestamp.between(start_date, end_date)
        ).scalar()

        # Render results
        return render_template(
            'statements.html',
            user_ssn=user_ssn,
            results=sorted_results,
            total_sent=total_sent,
            total_received=total_received
        )

    # Render the blank form for GET requests
    return render_template('statements.html')



@app.route('/bonus_statements', methods=['GET', 'POST'])
@login_required
def bonus_statements():
    if request.method == 'POST':
        user_ssn = request.form.get('ssn')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # Convert date inputs to datetime objects
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        # Query for transactions with the maximum amount of money
        max_transactions_query = db.session.query(Transaction).filter(
            Transaction.initiation_timestamp.between(start_date, end_date) if start_date and end_date else True
        ).order_by(Transaction.amount.desc()).first()

        if not max_transactions_query:
            max_transactions_query = {'transaction_id': 'N/A', 'amount': 'N/A', 'initiation_timestamp': 'N/A'}
        else:
            max_transactions_query = {
                'transaction_id': max_transactions_query.transaction_id,
                'amount': max_transactions_query.amount,
                'initiation_timestamp': max_transactions_query.initiation_timestamp
            }

        # Query for the best users by total money sent/received
        best_users_sent = db.session.query(
            WalletAccount.SSN,
            func.sum(Transaction.amount).label('total_sent')
        ).join(Transaction, Transaction.sender_wallet_id_ssn == WalletAccount.SSN).group_by(
            WalletAccount.SSN).order_by(func.sum(Transaction.amount).desc()).limit(5).all()

        best_users_received = db.session.query(
            WalletAccount.SSN,
            func.sum(Transaction.amount).label('total_received')
        ).join(Transaction, Transaction.receiver_wallet_id_ssn == WalletAccount.SSN).group_by(
            WalletAccount.SSN).order_by(func.sum(Transaction.amount).desc()).limit(5).all()

        # Render the template with the new data
        return render_template('bonus_statements.html', 
                               max_transactions=max_transactions_query, 
                               best_users_sent=best_users_sent,
                               best_users_received=best_users_received)

    # Render the blank form for GET requests
    return render_template('bonus_statements.html')


@app.route('/cancel_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def cancel_transaction(transaction_id):
    # Find the transaction
    transaction = Transaction.query.get(transaction_id)

    if not transaction:
        flash("Transaction not found.", "danger")
        return redirect(url_for('index'))

    # Check if the transaction is within 10 minutes
    # Check if the transaction is within 10 minutes
    time_diff = datetime.now() - transaction.initiation_timestamp
    if time_diff > timedelta(minutes=10):
        flash("Transaction is beyond the cancellation window and cannot be canceled.", "danger")
        return redirect(url_for('index'))


    # Cancel the transaction logic here
    transaction.status = "Cancelled"
    transaction.cancellation_reason = "User canceled the transaction."
    transaction.cancellation_timestamp = datetime.now()

    sender_wallet = WalletAccount.query.filter_by(SSN=transaction.sender_wallet_id_ssn).first()
    receiver_wallet = WalletAccount.query.filter_by(SSN=transaction.receiver_wallet_id_ssn).first()

    sender_wallet.balance += transaction.amount
    receiver_wallet.balance -= transaction.amount

    send_money_record = SendMoney.query.filter_by(transaction_id=transaction.transaction_id).first()
    if send_money_record:
        send_money_record.cancellation_reason = transaction.cancellation_reason
        send_money_record.cancellation_timestamp = transaction.cancellation_timestamp

    db.session.commit()

    flash("Transaction cancelled successfully.", "success")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

