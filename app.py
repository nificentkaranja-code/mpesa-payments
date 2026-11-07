from flask import Flask, request, jsonify, render_template, session, redirect
from lipa_mpesa import MpesaClient, MpesaConfig, SANDBOX_SHORTCODE
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_this_later'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///payments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# This creates the structure of our database table
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checkout_id = db.Column(db.String(100), unique=True)
    amount = db.Column(db.Integer)
    receipt_number = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    status = db.Column(db.String(20))

# Paste your actual keys here
client = MpesaClient(MpesaConfig(
    consumer_key="K8k3lCvZfuJ9OZo29CAKXYgmpf5ZjOWfFLNgKGewqEvHS55Y",
    consumer_secret="EDfO6kLGDiyvrcEFJdbYm6yLJVap5dOxhSxhv2aGwYGt4hd9loIGDtsSWpGPyG8G",
    environment="sandbox",
    shortcode=SANDBOX_SHORTCODE,
    passkey="bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",
    callback_url="https://mpesa-payments-3iyn.onrender.com/callback"
))
@app.route('/')
def home():
    return render_template('index.html')

# 1. The route to trigger the payment
@app.route('/pay', methods=['GET'])
def pay():
    phone = request.args.get('phone', '254710352607')
    amount = request.args.get('amount', 1)
    
    try:
        res = client.stk_push(
            phone=phone,
            amount=amount,
            account_reference="TEST"
        )
        return jsonify({"message": "Payment prompt sent!", "checkout_id": res.checkout_request_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 2. The route to catch Safaricom's callback
@app.route('/callback', methods=['POST'])   
def callback():
    data = request.get_json()
    print("\n--- CALLBACK RECEIVED FROM SAFARICOM ---")
    print(data)
    print("----------------------------------------\n")
    
    try:
        # Safaricom sends the data deeply nested in this dictionary
        stk = data['Body']['stkCallback']
        checkout_id = stk['CheckoutRequestID']
        result_code = stk['ResultCode']
        
        if result_code == 0:
            # Payment was successful!
            items = stk['CallbackMetadata']['Item']
            # Extract the amount and receipt number from the list
            amount = next((item['Value'] for item in items if item['Name'] == 'Amount'), 0)
            receipt = next((item['Value'] for item in items if item['Name'] == 'MpesaReceiptNumber'), 'N/A')
            
            # Save it to the database
            new_payment = Payment(
                checkout_id=checkout_id,
                amount=amount,
                receipt_number=receipt,
                status="Success"
            )
            db.session.add(new_payment)
            db.session.commit()
            print(f"✅ SAVED TO DATABASE! Receipt: {receipt}")
            
    except Exception as e:
        print("Error saving to database:", e)

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin123': # This is the password you will type to log in
            session['logged_in'] = True
            return redirect('/dashboard')
        else:
            return "Wrong password! Go back and try again."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/login') # If not logged in, kick them to the login page!
        
    payments = Payment.query.order_by(Payment.id.desc()).all()
    return render_template('dashboard.html', payments=payments)

# 3. The debug route
@app.route('/debug', methods=['GET'])
def debug():
    try:
        token = client.get_access_token(force_refresh=True)
        return jsonify({"message": "Keys are VALID!", "token_starts_with": token[:10]})
    except Exception as e:
        return jsonify({"error": str(e)})
# Create the database file if it doesn't exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(port=5000, debug=True)
