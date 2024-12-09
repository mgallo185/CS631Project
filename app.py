from flask import Flask, render_template, redirect, url_for, request, flash
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
    
    
class Email(db.Model):
    email_address = db.Column(db.String(255), primary_key=True)
    ssn = db.Column(db.String(9), db.ForeignKey('user.SSN'))
    isVerified = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='emails')




# Ensure tables are created if they don't exist
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  #


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
        identifier = request.form['identifier']  # This can be an SSN or email
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
            login_user(user)
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

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')  # Your profile page for logged-in users

if __name__ == '__main__':
    app.run(debug=True)
