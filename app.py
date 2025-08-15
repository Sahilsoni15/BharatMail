from flask import Flask, render_template, request, redirect, session, flash, jsonify
from datetime import datetime
import firebase
import re
import random
import os
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
app = Flask(__name__)
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)

@app.before_request
def make_session_permanent():
    session.permanent = True

app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Updated domain from @bharatmail.free.nf to @bharatmail.in for custom domain
EMAIL_SUFFIX = "@bharatmail.in"
UPLOAD_FOLDER = "static/profile_pics"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

from PIL import Image, ImageDraw, ImageFont
# Avatar background colors
AVATAR_COLORS = [
    "#FF5733", "#33A1FF", "#28A745", "#FFC300",
    "#8E44AD", "#FF69B4", "#20B2AA", "#FF4500"
]

# ---------------- Helper Functions ----------------
def is_valid_username(username):
    return re.match("^[a-zA-Z0-9]+$", username) is not None

def suggest_email(username):
    return f"{username}{random.randint(10, 99)}{EMAIL_SUFFIX}"

def categorize_mail(subject, message):
    subject_lower = subject.lower() if subject else ""
    message_lower = message.lower() if message else ""
    # Placeholder keywords for categorization
    promotions_keywords = ["sale", "discount", "offer", "deal", "promo"]
    social_keywords = ["friend", "party", "social", "invite", "like", "comment"]
    updates_keywords = ["update", "news", "alert", "notification", "reminder"]

    if any(word in subject_lower or word in message_lower for word in promotions_keywords):
        return "Promotions"
    elif any(word in subject_lower or word in message_lower for word in social_keywords):
        return "Social"
    elif any(word in subject_lower or word in message_lower for word in updates_keywords):
        return "Updates"
    else:
        return "Inbox"

def generate_avatar(first_name, last_name, font_path="DejaVuSans-Bold.ttf"):
    import base64
    from io import BytesIO
    
    initials = ((first_name[0] if first_name else "") + (last_name[0] if last_name else "")).upper()
    if not initials.strip():
        initials = "U"

    bg_color = random.choice(AVATAR_COLORS)
    # Create high-resolution image for better quality
    img_size = 400  # Increased from 120 to 400 for better quality
    img = Image.new("RGB", (img_size, img_size), bg_color)
    draw = ImageDraw.Draw(img)

    # Add subtle gradient effect
    
    # Create a subtle inner shadow/gradient effect
    overlay = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Add a subtle vignette effect
    for i in range(20):
        alpha = int(255 * (i / 20) * 0.1)  # Very subtle
        overlay_draw.ellipse(
            [i, i, img_size-i, img_size-i], 
            outline=None, 
            fill=(0, 0, 0, alpha)
        )
    
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

    # Dynamically pick the largest font size that fits well
    fontsize = int(img_size * 0.4)  # Adjusted proportion for larger image
    font = None
    while fontsize > 40:  # Minimum font size increased
        try:
            font = ImageFont.truetype(font_path, fontsize)
        except:
            font = ImageFont.load_default()
            break
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        # Leave appropriate padding
        if text_width < img_size * 0.7 and text_height < img_size * 0.7:
            break
        fontsize -= 8  # Larger steps for efficiency

    # Center the text with better positioning
    bbox = draw.textbbox((0, 0), initials, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (img_size - w) / 2
    y = (img_size - h) / 2 - (bbox[1] / 2)  # Adjust for font baseline
    
    # Add text shadow for depth
    shadow_offset = 2
    draw.text((x + shadow_offset, y + shadow_offset), initials, fill=(0, 0, 0, 30), font=font)
    
    # Draw main text
    draw.text((x, y), initials, fill="white", font=font)

    # Apply anti-aliasing by resizing if needed
    if img_size > 200:
        img = img.resize((200, 200), Image.Resampling.LANCZOS)

    # Convert to base64 data URL for cloud deployment compatibility
    buffer = BytesIO()
    img.save(buffer, format='PNG', quality=95)
    img_data = buffer.getvalue()
    img_base64 = base64.b64encode(img_data).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


# ---------------- Routes ----------------
@app.route("/")
def home():
    return redirect("/login")

# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        username = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        if not is_valid_username(username):
            flash("Email can contain only letters and numbers. No symbols or spaces!")
            return redirect("/register")

        email = f"{username}{EMAIL_SUFFIX}"
        if firebase.ref.child("users").child(email.replace(".", ",")).get():
            suggested = suggest_email(username)
            flash(f"Email already taken! Try: {suggested}")
            return redirect("/register")

        avatar_url = generate_avatar(first_name, last_name)

        firebase.ref.child("users").child(email.replace(".", ",")).set({
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "email": email,
            "password": password,
            "phone": "",
            "profile_pic": avatar_url,
            "created_at": str(datetime.now())
        })

        flash(f"Registration successful! Your email is {email}")
        return redirect("/login")
    return render_template("register.html")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    add_mode = request.args.get("add") == "1"  # ?add=1 means Add Account mode

    if request.method == "POST":
        email_or_username = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        if "@" in email_or_username:
            email = email_or_username
        else:
            email = f"{email_or_username}{EMAIL_SUFFIX}"

        email_key = email.replace(".", ",")
        user = firebase.ref.child("users").child(email_key).get()

        if user:
            if user['password'] == password:
                if not add_mode:
                    # Normal login clears everything
                    session.clear()

                session['user_email'] = email
                accounts = session.get('accounts', [])
                if email not in accounts:
                    accounts.append(email)
                session['accounts'] = accounts

                flash(f"Welcome {user['first_name']}! You are logged in as {email}")
                return redirect("/inbox")
            else:
                flash("Incorrect password! Try again.")
        else:
            flash(f"User '{email}' not found!")
        return redirect("/login")

    return render_template("login.html", add_mode=add_mode)

@app.route("/inbox")
def inbox():
    current_email = session.get('user_email')
    if not current_email:
        return redirect("/login")

    user_key = current_email.replace(".", ",")
    user = firebase.ref.child("users").child(user_key).get()

    # Fetch received messages from the user's inbox
    inbox_ref = firebase.ref.child("inbox").child(current_email.replace(".", ",")).get() or {}
    messages = []
    for key, m in inbox_ref.items():
        if m.get('receiver') == current_email:
            m['id'] = key
            messages.append(m)

    search_query = request.args.get("search", "").lower()
    if search_query:
        messages = [
            m for m in messages
            if search_query in m.get("subject", "").lower()
            or search_query in m.get("message", "").lower()
        ]

    # Categorize mails
    categorized_mails = {
        "Inbox": [],
        "Promotions": [],
        "Social": [],
        "Updates": []
    }
    for mail in messages:
        category = categorize_mail(mail.get("subject", ""), mail.get("message", ""))
        categorized_mails[category].append(mail)

    # Fetch Sent mails
    sent_messages_ref = firebase.ref.child("sent").child(user_key).get() or {}
    sent_messages = []
    for key, m in sent_messages_ref.items():
        m['id'] = key
        sent_messages.append(m)
    categorized_mails["Sent"] = sent_messages

    # Fetch Draft mails
    draft_messages = firebase.ref.child("drafts").child(user_key).get() or {}
    categorized_mails["Drafts"] = list(draft_messages.values())

    accounts = session.get('accounts', [])

    other_accounts = []
    for acc_email in accounts:
        if acc_email != current_email:
            acc_data = firebase.ref.child("users").child(acc_email.replace(".", ",")).get()
            if acc_data:
                other_accounts.append({
                    "email": acc_email,
                    "name": f"{acc_data.get('first_name', '')} {acc_data.get('last_name', '')}".strip()
                })

    colors = ["#ff5733", "#33a1ff", "#8e44ad", "#27ae60", "#f39c12"]
    profile_bg_color = random.choice(colors)

    # Create user_name with fallback
    first_name = user.get('first_name', '').strip()
    last_name = user.get('last_name', '').strip()
    user_name = f"{first_name} {last_name}".strip()
    
    # If user_name is empty, use email prefix as fallback
    if not user_name:
        user_name = current_email.split('@')[0].replace('.', ' ').title()

    return render_template(
        "inbox.html",
        messages=messages,
        user=user,
        user_email=current_email,
        user_name=user_name,
        user_first_name=first_name,
        user_last_name=last_name,
        user_profile_pic=user.get("profile_pic", None),
        profile_bg_color=profile_bg_color,
        accounts=accounts,
        search_query=search_query,
        other_accounts=other_accounts,
        categorized_mails=categorized_mails
    )

# Switch account
@app.route("/switch_account/<email>")
def switch_account(email):
    if email in session.get('accounts', []):
        session['user_email'] = email
    return redirect("/inbox")

# Compose with draft support and categorization on send
@app.route("/compose", methods=["GET", "POST"])
def compose():
    current_email = session.get('user_email')
    if not current_email:
        return redirect("/login")

    # Handle reply parameters
    reply_to = request.args.get('reply_to')
    subject_param = request.args.get('subject', '')
    message_param = request.args.get('message', '')
    forward = request.args.get('forward')
    
    if request.method == "POST":
        if "save_draft" in request.form:
            # Save draft logic
            draft_id = request.form.get("draft_id") or str(random.randint(100000,999999))
            receiver_username = request.form.get('receiver', "").strip().lower()
            receiver = f"{receiver_username}{EMAIL_SUFFIX}" if receiver_username else ""
            subject = request.form.get('subject', "")
            message = request.form.get('message', "")
            timestamp = str(datetime.now())

            draft_data = {
                "sender": current_email,
                "receiver": receiver,
                "subject": subject,
                "message": message,
                "attachments": [],  # attachments not saved in draft for simplicity
                "timestamp": timestamp
            }
            firebase.ref.child("drafts").child(current_email.replace(".", ",")).child(draft_id).set(draft_data)
            flash("Draft saved successfully!")
            return redirect("/compose")

        # Sending mail
        sender = current_email
        receiver_username = request.form['receiver'].strip().lower()
        receiver = f"{receiver_username}{EMAIL_SUFFIX}"
        subject = request.form['subject']
        message = request.form['message']
        timestamp = str(datetime.now())

        if not firebase.ref.child("users").child(receiver.replace(".", ",")).get():
            flash(f"Receiver {receiver} does not exist!")
            return redirect("/compose")

        # Save attachments
        attachments = []
        if 'attachments' in request.files:
            # Upload folder exist नहीं तो create कर दो
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

            files = request.files.getlist('attachments')
            for file in files:
                if file.filename:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    file.save(filepath)
                    attachments.append(f"/{filepath}")

        # Create mail data
        mail_data = {
            "sender": sender,
            "receiver": receiver,
            "subject": subject,
            "message": message,
            "attachments": attachments,
            "timestamp": timestamp
        }
        
        # Save in receiver's inbox
        receiver_key = receiver.replace(".", ",")
        firebase.ref.child("inbox").child(receiver_key).push(mail_data)
        
        # Save in sender's sent folder
        sender_key = sender.replace(".", ",")
        firebase.ref.child("sent").child(sender_key).push(mail_data)
        flash("Message sent successfully!")
        return redirect("/inbox")

    # Pass reply parameters to template
    reply_data = {
        'reply_to': reply_to,
        'subject': subject_param,
        'message': message_param,
        'forward': forward
    }

    return render_template("compose.html", reply_data=reply_data)

# Draft save/fetch API
@app.route("/draft", methods=["GET", "POST"])
def draft():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({"error": "Not logged in"}), 401

    user_key = current_email.replace(".", ",")

    if request.method == "POST":
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        draft_id = data.get("draft_id") or str(random.randint(100000,999999))
        draft_data = {
            "sender": current_email,
            "receiver": data.get("receiver", ""),
            "subject": data.get("subject", ""),
            "message": data.get("message", ""),
            "attachments": data.get("attachments", []),
            "timestamp": str(datetime.now())
        }
        firebase.ref.child("drafts").child(user_key).child(draft_id).set(draft_data)
        return jsonify({"message": "Draft saved", "draft_id": draft_id})

    else:  # GET
        drafts = firebase.ref.child("drafts").child(user_key).get() or {}
        return jsonify(drafts)

# Profile View
@app.route("/profile")
def profile():
    user_email = session.get('user_email')
    if not user_email:
        return redirect("/login")

    user = firebase.ref.child("users").child(user_email.replace(".", ",")).get()
    
    # Generate profile background color
    colors = ["#ff5733", "#33a1ff", "#8e44ad", "#27ae60", "#f39c12"]
    profile_bg_color = random.choice(colors)
    
    # Create user_name with fallback
    first_name = user.get('first_name', '').strip()
    last_name = user.get('last_name', '').strip()
    user_name = f"{first_name} {last_name}".strip()
    
    # If user_name is empty, use email prefix as fallback
    if not user_name:
        user_name = user_email.split('@')[0].replace('.', ' ').title()
        # Also set fallback first/last names for initials
        name_parts = user_name.split()
        first_name = name_parts[0] if name_parts else 'U'
        last_name = name_parts[1] if len(name_parts) > 1 else 'N'
    
    return render_template(
        "profile.html",
        user=user,
        user_email=user_email,
        user_name=user_name,
        user_first_name=first_name,
        user_last_name=last_name,
        user_phone=user.get("phone", ""),
        user_profile_pic=user.get("profile_pic", None),
        profile_bg_color=profile_bg_color
    )

# Profile Update
@app.route("/update_profile", methods=["POST"])
def update_profile():
    user_email = session.get("user_email")
    if not user_email:
        return redirect("/login")

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "").strip()
    remove_pic = request.form.get("remove_pic") == "on"

    parts = name.split(" ", 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    user_ref = firebase.ref.child("users").child(user_email.replace(".", ","))
    updates = {"first_name": first_name, "last_name": last_name, "phone": phone}

    if password:
        updates["password"] = password

    if remove_pic:
        updates["profile_pic"] = generate_avatar(first_name, last_name)
    elif "profile_pic" in request.files:
        file = request.files["profile_pic"]
        if file and file.filename:
            try:
                import base64
                from io import BytesIO
                
                # Reset file pointer to beginning
                file.seek(0)
                
                # Open the uploaded image
                img = Image.open(file)

                # Crop to square (center crop)
                width, height = img.size
                min_dim = min(width, height)
                left = (width - min_dim) / 2
                top = (height - min_dim) / 2
                right = (width + min_dim) / 2
                bottom = (height + min_dim) / 2
                img = img.crop((left, top, right, bottom))

                # Resize to standard profile size
                img = img.resize((200, 200))

                # Convert to base64 data URL for cloud deployment compatibility
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                img_data = buffer.getvalue()
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                updates["profile_pic"] = f"data:image/png;base64,{img_base64}"
                
                flash("Profile picture updated successfully!")
            except Exception as e:
                print(f"Error processing profile picture: {e}")
                flash("Error updating profile picture. Please try again.")

    user_ref.update(updates)
    flash("Profile updated successfully!")
    return redirect("/profile")

# Logout specific account
@app.route("/logout/<email>")
def logout_specific(email):
    accounts = session.get('accounts', [])
    if email in accounts:
        accounts.remove(email)
    session['accounts'] = accounts

    if session.get('user_email') == email:
        if accounts:
            session['user_email'] = accounts[0]
            flash(f"Logged out from {email} — switched to {accounts[0]}")
            return redirect("/inbox")
        else:
            session.pop('user_email', None)
            flash(f"Logged out from {email}")
            return redirect("/login")

    flash(f"Logged out from {email}")
    return redirect("/inbox")

@app.route("/manage_profile")
def manage_profile():
    return redirect("/profile")
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!")
    return redirect("/login")

# Delete Account
@app.route("/delete_account", methods=["POST"])
def delete_account():
    user_email = session.get("user_email")
    if not user_email:
        flash("No user logged in!")
        return redirect("/login")

    # Remove user from Firebase
    user_key = user_email.replace(".", ",")
    firebase.ref.child("users").child(user_key).delete()

    # Optionally, remove user's inbox messages
    inbox_ref = firebase.ref.child("inbox").get() or {}
    for key, msg in inbox_ref.items():
        if msg.get("sender") == user_email or msg.get("receiver") == user_email:
            firebase.ref.child("inbox").child(key).delete()

    # Remove user from session and accounts list
    accounts = session.get("accounts", [])
    if user_email in accounts:
        accounts.remove(user_email)
    session['accounts'] = accounts
    session.pop('user_email', None)

    flash(f"Account {user_email} deleted successfully!")
    return redirect("/login")
@app.route("/send_mail", methods=["POST"])
def send_mail():
    current_email = session.get('user_email')
    if not current_email:
        return redirect("/login")

    to_email = request.form.get('to')
    cc_email = request.form.get('cc')
    bcc_email = request.form.get('bcc')
    subject = request.form.get('subject')
    message = request.form.get('message')

    # Handle attachments
    attachments = request.files.getlist('attachments')
    saved_attachments = []

    # <-- Add this line to create uploads folder if missing
    os.makedirs("./uploads", exist_ok=True)

    for file in attachments:
        if file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join("./uploads", filename)
            file.save(filepath)
            saved_attachments.append(f"/{filepath}")

    # Create mail data
    mail_data = {
        "sender": current_email,
        "receiver": to_email,
        "cc": cc_email,
        "bcc": bcc_email,
        "subject": subject,
        "message": message,
        "attachments": saved_attachments,
        "timestamp": str(datetime.now())
    }

    # Save in receiver's inbox
    receiver_key = to_email.replace(".", ",")
    firebase.ref.child("inbox").child(receiver_key).push(mail_data)
    
    # Save in sender's sent folder
    user_key = current_email.replace(".", ",")
    firebase.ref.child("sent").child(user_key).push(mail_data)

    flash("Mail sent successfully!")
    return redirect("/inbox")

@app.route("/read/<mail_id>")
def read_mail(mail_id):
    current_email = session.get('user_email')
    if not current_email:
        return redirect("/login")

    user_key = current_email.replace(".", ",")
    inbox = firebase.ref.child("inbox").child(user_key).get() or {}
    mail = inbox.get(mail_id)

    if not mail:
        sent = firebase.ref.child("sent").child(user_key).get() or {}
        mail = sent.get(mail_id)

    if not mail:
        drafts = firebase.ref.child("drafts").child(user_key).get() or {}
        mail = drafts.get(mail_id)

    if not mail:
        flash("Mail not found.")
        return redirect("/inbox")

    return render_template("read_mail.html", mail=mail)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
