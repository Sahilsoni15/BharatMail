from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_from_directory
from datetime import datetime, timedelta
import firebase
import re
import random
import os
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
import time
import secrets
from functools import wraps
app = Flask(__name__)
app.permanent_session_lifetime = timedelta(days=60)  # Session expires after 60 days

# Configure session security
app.config.update(
    SESSION_COOKIE_SECURE=True if os.environ.get('HTTPS') == 'true' else False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=60)
)

@app.before_request
def make_session_permanent():
    session.permanent = True
    
    # Check for session timeout
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(days=60):
            session.clear()
            flash('Session expired. Please log in again.')
            return redirect('/login')
    
    # Update last activity timestamp
    session['last_activity'] = datetime.now().isoformat()

app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Rate limiting storage
request_counts = {}
CSRF_SECRET_KEY = os.environ.get('CSRF_SECRET_KEY', secrets.token_urlsafe(32))

# Rate limiting decorator
def rate_limit(max_requests=10, per_seconds=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_email', request.remote_addr)
            current_time = time.time()
            
            # Clean old entries
            if user_id in request_counts:
                request_counts[user_id] = [
                    timestamp for timestamp in request_counts[user_id]
                    if current_time - timestamp < per_seconds
                ]
            else:
                request_counts[user_id] = []
            
            # Check rate limit
            if len(request_counts[user_id]) >= max_requests:
                return jsonify({'error': 'Rate limit exceeded. Please wait a moment.'}), 429
            
            # Add current request
            request_counts[user_id].append(current_time)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# CSRF token generation
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']

# CSRF validation
def validate_csrf_token(token):
    return token and 'csrf_token' in session and secrets.compare_digest(session['csrf_token'], token)

# Template context processor
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)

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

def get_user_avatar_data(email):
    """Get user avatar data (initials, color, avatar image)"""
    if not email:
        return {
            'initials': 'U',
            'avatar_color': '#666666',
            'avatar': None
        }
    
    try:
        user_key = email.replace(".", ",")
        user_data = firebase.ref.child("users").child(user_key).get()
        
        if user_data:
            first_name = user_data.get('first_name', '').strip()
            last_name = user_data.get('last_name', '').strip()
            
            # Generate initials
            if first_name and last_name:
                initials = (first_name[0] + last_name[0]).upper()
            elif first_name:
                initials = first_name[:2].upper()
            elif last_name:
                initials = last_name[:2].upper()
            else:
                initials = email[:2].upper()
            
            # Generate consistent background color based on email
            colors = ['#FF5733', '#33A1FF', '#28A745', '#FFC300', '#8E44AD', '#FF69B4', '#20B2AA', '#FF4500']
            color_index = sum(ord(c) for c in email) % len(colors)
            
            return {
                'initials': initials,
                'avatar_color': colors[color_index],
                'avatar': user_data.get('profile_pic'),
                'name': f"{first_name} {last_name}".strip() or email.split('@')[0].replace('.', ' ').title()
            }
    except Exception as e:
        print(f"Error getting user avatar data for {email}: {e}")
    
    # Fallback
    return {
        'initials': email[:2].upper() if email else 'U',
        'avatar_color': '#666666',
        'avatar': None,
        'name': email.split('@')[0].replace('.', ' ').title() if email else 'Unknown'
    }

def format_time(timestamp_str):
    """Format timestamp for display"""
    try:
        if not timestamp_str:
            return "Unknown"
        
        # Parse timestamp - handle microseconds and different formats
        if 'T' in timestamp_str:
            # ISO format - remove microseconds if present
            timestamp_str = timestamp_str.split('.')[0] if '.' in timestamp_str else timestamp_str
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            # Legacy format - handle microseconds
            if '.' in timestamp_str:
                timestamp_str = timestamp_str.split('.')[0]
            try:
                dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Try other possible formats
                try:
                    dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    # If all parsing fails, return original
                    return timestamp_str
        
        now = datetime.now()
        diff = now - dt.replace(tzinfo=None) if dt.tzinfo else now - dt
        
        if diff.days == 0:
            if diff.seconds < 3600:  # Less than 1 hour
                minutes = diff.seconds // 60
                return f"{minutes}m ago" if minutes > 0 else "Just now"
            else:
                hours = diff.seconds // 3600
                return f"{hours}h ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime('%b %d')
            
    except Exception as e:
        print(f"Error formatting time {timestamp_str}: {e}")
        return "Unknown"

def parse_timestamp_for_sorting(timestamp_str):
    """Parse timestamp for sorting purposes - returns datetime object"""
    try:
        if not timestamp_str:
            return datetime.min
        
        # Parse timestamp - handle microseconds and different formats
        if 'T' in timestamp_str:
            # ISO format - remove microseconds if present
            timestamp_str = timestamp_str.split('.')[0] if '.' in timestamp_str else timestamp_str
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            # Legacy format - handle microseconds
            if '.' in timestamp_str:
                timestamp_str = timestamp_str.split('.')[0]
            try:
                return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Try other possible formats
                try:
                    return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    # If all parsing fails, return minimum datetime
                    print(f"Warning: Could not parse timestamp for sorting: {timestamp_str}")
                    return datetime.min
            
    except Exception as e:
        print(f"Error parsing timestamp for sorting {timestamp_str}: {e}")
        return datetime.min

def enhance_email_data(mail, current_email):
    """Enhance email data with avatar, name, and formatted time"""
    try:
        # Add formatted time
        mail['formatted_time'] = format_time(mail.get('timestamp'))
        
        # Add message preview
        message = mail.get('message', '')
        mail['message_preview'] = message[:100] + '...' if len(message) > 100 else message
        
        # Always get sender data
        sender_email = mail.get('sender')
        if sender_email:
            sender_data = get_user_avatar_data(sender_email)
            mail['sender_name'] = sender_data['name']
            mail['sender_initials'] = sender_data['initials']
            mail['sender_avatar_color'] = sender_data['avatar_color']
            mail['sender_avatar'] = sender_data['avatar']
        
        # Always get receiver data
        receiver_email = mail.get('receiver')
        if receiver_email:
            receiver_data = get_user_avatar_data(receiver_email)
            mail['receiver_name'] = receiver_data['name']
            mail['receiver_initials'] = receiver_data['initials']
            mail['receiver_avatar_color'] = receiver_data['avatar_color']
            mail['receiver_avatar'] = receiver_data['avatar']
        
    except Exception as e:
        print(f"Error enhancing email data: {e}")
    
    return mail

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
                    print(f"\n=== NORMAL LOGIN ===")
                    print(f"Clearing session and logging in: {email}")
                    session.clear()
                    session['user_email'] = email
                    accounts = [email]  # Start fresh with just this account
                    session['accounts'] = accounts
                    print(f"Session after normal login: {dict(session)}")
                    flash(f"Welcome {user['first_name']}! You are now logged in as {email}")
                else:
                    # Add account mode - preserve existing sessions
                    print(f"\n=== ADD ACCOUNT MODE ===")
                    current_user = session.get('user_email')
                    print(f"Current user before adding: {current_user}")
                    print(f"Session before adding account: {dict(session)}")
                    print(f"Adding account: {email}")
                    
                    session['user_email'] = email  # Switch to new account immediately
                    accounts = session.get('accounts', [])
                    print(f"Existing accounts: {accounts}")
                    if email not in accounts:
                        accounts.append(email)
                        print(f"Added {email} to accounts list")
                    else:
                        print(f"{email} already in accounts list")
                    session['accounts'] = accounts
                    print(f"Final accounts list: {accounts}")
                    print(f"Session after adding account: {dict(session)}")
                    
                    if current_user:
                        flash(f"Account {email} added successfully! You are now using {email}. You can switch back to {current_user} anytime.")
                    else:
                        flash(f"Welcome {user['first_name']}! You are now logged in as {email}")
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
    
    # Categorize mails and enhance with avatar data
    categorized_mails = {
        "Inbox": [],
        "Promotions": [],
        "Social": [],
        "Updates": []
    }
    
    # Enhance all messages first
    enhanced_messages = []
    for mail in messages:
        enhanced_mail = enhance_email_data(mail, current_email)
        enhanced_messages.append(enhanced_mail)
    
    # Debug: Print first few timestamps to see the format
    if enhanced_messages:
        print(f"\n=== TIMESTAMP DEBUG ===")
        for i, msg in enumerate(enhanced_messages[:3]):
            print(f"Message {i+1}: {msg.get('timestamp')} -> {msg.get('formatted_time')}")
        print(f"=== END TIMESTAMP DEBUG ===\n")
    
    # Sort enhanced messages by timestamp (newest first)
    try:
        enhanced_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        print(f"Sorted {len(enhanced_messages)} messages by timestamp")
        
        # Debug: Show first few sorted messages
        if enhanced_messages:
            print(f"\n=== SORTED MESSAGES DEBUG ===")
            for i, msg in enumerate(enhanced_messages[:5]):
                timestamp = msg.get('timestamp', 'Unknown')
                formatted_time = msg.get('formatted_time', 'Unknown')
                print(f"Message {i+1}: {timestamp} -> {formatted_time}")
            print(f"=== END SORTED MESSAGES DEBUG ===\n")
            
    except Exception as e:
        print(f"Error sorting messages: {e}")
        # Fallback sorting if timestamp format is different
        enhanced_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        print(f"Sorted {len(enhanced_messages)} messages by string timestamp")
    
    # Apply search filter if needed
    search_query = request.args.get("search", "").lower()
    if search_query:
        enhanced_messages = [
            m for m in enhanced_messages
            if search_query in m.get("subject", "").lower()
            or search_query in m.get("message", "").lower()
        ]
    
    # Categorize the sorted messages
    for enhanced_mail in enhanced_messages:
        category = categorize_mail(enhanced_mail.get("subject", ""), enhanced_mail.get("message", ""))
        categorized_mails[category].append(enhanced_mail)

    # Fetch Sent mails
    sent_messages_ref = firebase.ref.child("sent").child(user_key).get() or {}
    sent_messages = []
    for key, m in sent_messages_ref.items():
        m['id'] = key
        sent_messages.append(m)
    
    # Enhance sent messages first
    enhanced_sent_messages = []
    for mail in sent_messages:
        enhanced_mail = enhance_email_data(mail, current_email)
        enhanced_sent_messages.append(enhanced_mail)
    
    # Sort enhanced sent messages by timestamp (newest first)
    try:
        enhanced_sent_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        print(f"Sorted {len(enhanced_sent_messages)} sent messages by timestamp")
    except Exception as e:
        print(f"Error sorting sent messages: {e}")
        enhanced_sent_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        print(f"Sorted {len(enhanced_sent_messages)} sent messages by string timestamp")
    
    categorized_mails["Sent"] = enhanced_sent_messages

    # Fetch Draft mails
    draft_messages_ref = firebase.ref.child("drafts").child(user_key).get() or {}
    draft_messages = []
    for key, m in draft_messages_ref.items():
        m['id'] = key
        draft_messages.append(m)
    
    # Enhance draft messages first
    enhanced_draft_messages = []
    for mail in draft_messages:
        enhanced_mail = enhance_email_data(mail, current_email)
        enhanced_draft_messages.append(enhanced_mail)
    
    # Sort enhanced draft messages by timestamp (newest first)
    try:
        enhanced_draft_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        print(f"Sorted {len(enhanced_draft_messages)} draft messages by timestamp")
    except Exception as e:
        print(f"Error sorting draft messages: {e}")
        enhanced_draft_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        print(f"Sorted {len(enhanced_draft_messages)} draft messages by string timestamp")
    
    categorized_mails["Drafts"] = enhanced_draft_messages

    accounts = session.get('accounts', [])
    
    # Debug information
    print(f"\n=== DEBUG ACCOUNT INFO ===")
    print(f"Current email: {current_email}")
    print(f"All accounts in session: {accounts}")
    print(f"Session contents: {dict(session)}")

    other_accounts = []
    for acc_email in accounts:
        if acc_email != current_email:
            print(f"Processing other account: {acc_email}")
            acc_data = firebase.ref.child("users").child(acc_email.replace(".", ",")).get()
            if acc_data:
                account_name = f"{acc_data.get('first_name', '')} {acc_data.get('last_name', '')}".strip()
                if not account_name:
                    account_name = acc_email.split('@')[0].replace('.', ' ').title()
                other_accounts.append({
                    "email": acc_email,
                    "name": account_name
                })
                print(f"Added account: {acc_email} -> {account_name}")
            else:
                print(f"No user data found for: {acc_email}")
    
    print(f"Final other_accounts: {other_accounts}")
    print(f"=== END DEBUG ===")

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
        previous_email = session.get('user_email')
        session['user_email'] = email
        # Get user info for better messaging
        user_data = firebase.ref.child("users").child(email.replace(".", ",")).get()
        if user_data:
            user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            if not user_name:
                user_name = email.split('@')[0]
            flash(f"Switched to {user_name} ({email})")
        else:
            flash(f"Switched to {email}")
    else:
        flash(f"Cannot switch to {email} - account not found in your logged in accounts")
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
        receiver_input = request.form['receiver'].strip().lower() if 'receiver' in request.form else request.form['to'].strip().lower()
        
        # Handle full email addresses or just usernames
        if "@" in receiver_input:
            receiver = receiver_input
        else:
            receiver = f"{receiver_input}{EMAIL_SUFFIX}"
            
        subject = request.form['subject']
        message = request.form['message']
        timestamp = str(datetime.now())

        if not firebase.ref.child("users").child(receiver.replace(".", ",")).get():
            flash(f"Receiver {receiver} does not exist!")
            return redirect("/compose")

        # Save attachments to uploads folder
        attachments = []
        upload_folder = "uploads"
        os.makedirs(upload_folder, exist_ok=True)
        
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    # Add timestamp to prevent conflicts
                    timestamp_str = str(int(datetime.now().timestamp()))
                    name, ext = os.path.splitext(filename)
                    unique_filename = f"{name}_{timestamp_str}{ext}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)
                    attachments.append(unique_filename)  # Store unique filename

        # Create mail data
        mail_data = {
            "sender": sender,
            "receiver": receiver,
            "subject": subject,
            "message": message,
            "attachments": attachments,
            "timestamp": timestamp,
            "is_reply": bool(reply_to),  # Track if this is a reply
            "cc": request.form.get('cc', ''),  # Include CC if provided
            "bcc": request.form.get('bcc', '')  # Include BCC if provided
        }
        
        print(f"\n=== SENDING MAIL ===")
        print(f"From: {sender}")
        print(f"To: {receiver}")
        print(f"Subject: {subject}")
        print(f"Attachments: {attachments}")
        print(f"Is Reply: {bool(reply_to)}")
        
        # Save in receiver's inbox
        receiver_key = receiver.replace(".", ",")
        inbox_ref = firebase.ref.child("inbox").child(receiver_key).push(mail_data)
        mail_data['id'] = inbox_ref.key  # Add the mail ID for notifications
        print(f"Saved to receiver inbox: {inbox_ref.key}")
        
        # Save in sender's sent folder
        sender_key = sender.replace(".", ",")
        sent_ref = firebase.ref.child("sent").child(sender_key).push(mail_data)
        print(f"Saved to sender sent: {sent_ref.key}")
        
        # Send push notification to receiver
        send_push_notification(receiver, mail_data)
        
        print(f"=== END SENDING MAIL ===")
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

    print(f"\n=== PROFILE UPDATE DEBUG ====")
    print(f"User: {user_email}")
    print(f"Form data: {dict(request.form)}")
    print(f"Files in request: {list(request.files.keys())}")
    
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
        print("Password will be updated")

    # Handle profile picture
    profile_pic_updated = False
    if remove_pic:
        print("Removing profile picture and generating new avatar")
        updates["profile_pic"] = generate_avatar(first_name, last_name)
        profile_pic_updated = True
    elif "profile_pic" in request.files:
        file = request.files["profile_pic"]
        print(f"Profile pic file: {file}")
        print(f"Filename: {getattr(file, 'filename', 'No filename attr')}")
        print(f"Content type: {getattr(file, 'content_type', 'No content_type attr')}")
        print(f"Content length: {getattr(file, 'content_length', 'No content_length attr')}")
        
        if file and hasattr(file, 'filename') and file.filename and file.filename.strip():
            try:
                print(f"Processing uploaded file: {file.filename}")
                import base64
                from io import BytesIO
                
                # Reset file pointer to beginning
                file.seek(0)
                file_data = file.read()
                print(f"File size: {len(file_data)} bytes")
                
                if len(file_data) == 0:
                    print("ERROR: File data is empty!")
                    flash("Uploaded file is empty. Please try again.")
                else:
                    # Reset file pointer and open image
                    file.seek(0)
                    img = Image.open(file)
                    print(f"Image opened successfully. Size: {img.size}, Mode: {img.mode}")

                    # Crop to square (center crop)
                    width, height = img.size
                    min_dim = min(width, height)
                    left = (width - min_dim) / 2
                    top = (height - min_dim) / 2
                    right = (width + min_dim) / 2
                    bottom = (height + min_dim) / 2
                    img = img.crop((left, top, right, bottom))
                    print(f"Image cropped to: {img.size}")

                    # Resize to standard profile size
                    img = img.resize((200, 200))
                    print(f"Image resized to: {img.size}")

                    # Convert to base64 data URL for cloud deployment compatibility
                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    img_data = buffer.getvalue()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    data_url = f"data:image/png;base64,{img_base64}"
                    print(f"Base64 data URL created, length: {len(data_url)}")
                    
                    updates["profile_pic"] = data_url
                    profile_pic_updated = True
                    flash("Profile picture updated successfully!")
                    print("Profile picture processing completed successfully")
                    
            except Exception as e:
                print(f"ERROR processing profile picture: {e}")
                import traceback
                traceback.print_exc()
                flash(f"Error updating profile picture: {str(e)}")
        else:
            print("No valid file uploaded for profile picture")
    else:
        print("No profile_pic in request.files")

    print(f"Final updates to be saved: {list(updates.keys())}")
    print(f"Profile pic updated: {profile_pic_updated}")
    
    try:
        user_ref.update(updates)
        print("Database update completed successfully")
        flash("Profile updated successfully!")
    except Exception as e:
        print(f"ERROR updating database: {e}")
        flash(f"Error saving profile: {str(e)}")
    
    print("=== END PROFILE UPDATE DEBUG ====\n")
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

    # Create uploads folder if missing
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    for file in attachments:
        if file and file.filename:
            filename = secure_filename(file.filename)
            # Add timestamp to prevent conflicts
            timestamp_str = str(int(datetime.now().timestamp()))
            name, ext = os.path.splitext(filename)
            unique_filename = f"{name}_{timestamp_str}{ext}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            saved_attachments.append(unique_filename)  # Store just filename

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
    inbox_ref = firebase.ref.child("inbox").child(receiver_key).push(mail_data)
    mail_data['id'] = inbox_ref.key  # Add the mail ID for notifications
    
    # Save in sender's sent folder
    user_key = current_email.replace(".", ",")
    firebase.ref.child("sent").child(user_key).push(mail_data)
    
    # Send push notification to receiver
    send_push_notification(to_email, mail_data)

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

    # Enhance mail data with avatar and name information
    enhanced_mail = enhance_email_data(mail, current_email)
    
    # Add formatted timestamp
    enhanced_mail['formatted_timestamp'] = format_time(mail.get('timestamp'))

    return render_template("read_mail.html", mail=enhanced_mail)

# Route to serve uploaded attachments
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Serve uploaded attachment files"""
    upload_folder = "uploads"
    file_path = os.path.join(upload_folder, filename)
    if not os.path.exists(file_path):
        # Return 404 error for missing files
        from flask import abort
        abort(404)
    return send_from_directory(upload_folder, filename)

# Notification subscription management
@app.route("/api/subscribe", methods=["POST"])
def subscribe_notifications():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CSRF token
    csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
        
    try:
        data = request.get_json()
        if not data or 'subscription' not in data:
            return jsonify({'error': 'Invalid subscription data'}), 400
            
        subscription = data['subscription']
        user_key = current_email.replace(".", ",")
        
        # Store subscription in Firebase
        firebase.ref.child("notifications").child(user_key).set({
            'subscription': subscription,
            'enabled': True,
            'created_at': str(datetime.now()),
            'user_email': current_email
        })
        
        return jsonify({'success': True, 'message': 'Notification subscription saved'})
        
    except Exception as e:
        print(f"Error saving notification subscription: {e}")
        return jsonify({'error': 'Failed to save subscription'}), 500

@app.route("/api/unsubscribe", methods=["POST"])
def unsubscribe_notifications():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CSRF token
    csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
        
    try:
        user_key = current_email.replace(".", ",")
        
        # Update subscription status in Firebase
        firebase.ref.child("notifications").child(user_key).update({
            'enabled': False,
            'updated_at': str(datetime.now())
        })
        
        return jsonify({'success': True, 'message': 'Notifications disabled'})
        
    except Exception as e:
        print(f"Error disabling notifications: {e}")
        return jsonify({'error': 'Failed to disable notifications'}), 500

@app.route("/api/notification-status", methods=["GET"])
def get_notification_status():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
        
    try:
        user_key = current_email.replace(".", ",")
        notification_data = firebase.ref.child("notifications").child(user_key).get()
        
        if notification_data:
            return jsonify({
                'enabled': notification_data.get('enabled', False),
                'subscribed': bool(notification_data.get('subscription'))
            })
        else:
            return jsonify({'enabled': False, 'subscribed': False})
            
    except Exception as e:
        print(f"Error getting notification status: {e}")
        return jsonify({'error': 'Failed to get notification status'}), 500

# Function to send push notification (called when new email arrives)
def send_push_notification(user_email, mail_data):
    """Send push notification to user when they receive a new email"""
    try:
        user_key = user_email.replace(".", ",")
        notification_data = firebase.ref.child("notifications").child(user_key).get()
        
        if not notification_data or not notification_data.get('enabled'):
            print(f"Notifications not enabled for {user_email}")
            return
            
        subscription = notification_data.get('subscription')
        if not subscription:
            print(f"No subscription found for {user_email}")
            return
            
        # Format notification message
        sender = mail_data.get('sender', 'Unknown')
        subject = mail_data.get('subject', '(No subject)')
        
        notification_payload = {
            'title': f'New email from {sender}',
            'body': subject,
            'icon': '/static/logo.png',
            'badge': '/static/logo.png',
            'url': '/inbox',
            'mailId': mail_data.get('id')
        }
        
        # Here you would integrate with a push service like FCM, OneSignal, etc.
        # For now, we'll just log the notification
        print(f"\n=== PUSH NOTIFICATION ===")
        print(f"To: {user_email}")
        print(f"Title: {notification_payload['title']}")
        print(f"Body: {notification_payload['body']}")
        print(f"=== END NOTIFICATION ===")
        
        # In a real implementation, you would send the notification here:
        # send_to_push_service(subscription, notification_payload)
        
    except Exception as e:
        print(f"Error sending push notification: {e}")

# Check for new emails API (for real-time checking)
@app.route("/api/check-new-emails", methods=["POST"])
@rate_limit(max_requests=30, per_seconds=60)  # Allow 30 checks per minute
def check_new_emails():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CSRF token
    csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    try:
        user_key = current_email.replace(".", ",")
        
        # Get last check timestamp from session or use 5 minutes ago
        last_check = session.get('last_email_check')
        if last_check:
            last_check_time = datetime.fromisoformat(last_check)
        else:
            last_check_time = datetime.now() - timedelta(minutes=5)
            
        # Fetch recent messages
        inbox_ref = firebase.ref.child("inbox").child(user_key).get() or {}
        new_emails = []
        
        for key, m in inbox_ref.items():
            if m.get('receiver') == current_email:
                email_time = datetime.fromisoformat(m.get('timestamp', '2000-01-01T00:00:00'))
                if email_time > last_check_time:
                    m['id'] = key
                    new_emails.append(m)
        
        # Update last check timestamp
        session['last_email_check'] = datetime.now().isoformat()
        
        return jsonify({
            'success': True,
            'new_emails': len(new_emails),
            'emails': new_emails[:5]  # Return max 5 new emails
        })
        
    except Exception as e:
        print(f"Error checking new emails: {e}")
        return jsonify({'error': 'Failed to check new emails'}), 500

# Secure refresh API endpoint
@app.route("/api/refresh", methods=["POST"])
@rate_limit(max_requests=15, per_seconds=60)  # Allow 15 refreshes per minute
def refresh_emails():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CSRF token
    csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    try:
        user_key = current_email.replace(".", ",")
        
        # Fetch received messages from the user's inbox
        inbox_ref = firebase.ref.child("inbox").child(user_key).get() or {}
        messages = []
        for key, m in inbox_ref.items():
            if m.get('receiver') == current_email:
                m['id'] = key
                messages.append(m)
        
        # Sort messages by timestamp (newest first)
        try:
            messages.sort(key=lambda x: datetime.fromisoformat(x.get('timestamp', '1970-01-01T00:00:00')), reverse=True)
        except:
            try:
                # Try legacy format
                messages.sort(key=lambda x: datetime.strptime(x.get('timestamp', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=True)
            except:
                # Fallback sorting if timestamp format is different
                messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Categorize mails and enhance with avatar data
        categorized_mails = {
            "Inbox": [],
            "Promotions": [],
            "Social": [],
            "Updates": []
        }
        
        # Enhance all messages first
        enhanced_messages = []
        for mail in messages:
            enhanced_mail = enhance_email_data(mail, current_email)
            enhanced_messages.append(enhanced_mail)
        
        # Sort enhanced messages by timestamp (newest first)
        try:
            enhanced_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        except Exception as e:
            print(f"Error sorting messages in refresh: {e}")
            # Fallback sorting if timestamp format is different
            enhanced_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Categorize the sorted messages
        for enhanced_mail in enhanced_messages:
            category = categorize_mail(enhanced_mail.get("subject", ""), enhanced_mail.get("message", ""))
            categorized_mails[category].append(enhanced_mail)
        
        # Fetch Sent mails
        sent_messages_ref = firebase.ref.child("sent").child(user_key).get() or {}
        sent_messages = []
        for key, m in sent_messages_ref.items():
            m['id'] = key
            sent_messages.append(m)
        
        # Sort sent messages by timestamp (newest first)
        try:
            sent_messages.sort(key=lambda x: datetime.fromisoformat(x.get('timestamp', '1970-01-01T00:00:00')), reverse=True)
        except:
            try:
                # Try legacy format
                sent_messages.sort(key=lambda x: datetime.strptime(x.get('timestamp', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=True)
            except:
                sent_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Enhance sent messages first
        enhanced_sent_messages = []
        for mail in sent_messages:
            enhanced_mail = enhance_email_data(mail, current_email)
            enhanced_sent_messages.append(enhanced_mail)
        
        # Sort enhanced sent messages by timestamp (newest first)
        try:
            enhanced_sent_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        except Exception as e:
            print(f"Error sorting sent messages in refresh: {e}")
            enhanced_sent_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        categorized_mails["Sent"] = enhanced_sent_messages
        
        # Fetch Draft mails
        draft_messages_ref = firebase.ref.child("drafts").child(user_key).get() or {}
        draft_messages = []
        for key, m in draft_messages_ref.items():
            m['id'] = key
            draft_messages.append(m)
        
        # Sort draft messages by timestamp (newest first)
        try:
            draft_messages.sort(key=lambda x: datetime.fromisoformat(x.get('timestamp', '1970-01-01T00:00:00')), reverse=True)
        except:
            try:
                # Try legacy format
                draft_messages.sort(key=lambda x: datetime.strptime(x.get('timestamp', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=True)
            except:
                draft_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Enhance draft messages first
        enhanced_draft_messages = []
        for mail in draft_messages:
            enhanced_mail = enhance_email_data(mail, current_email)
            enhanced_draft_messages.append(enhanced_mail)
        
        # Sort enhanced draft messages by timestamp (newest first)
        try:
            enhanced_draft_messages.sort(key=lambda x: parse_timestamp_for_sorting(x.get('timestamp')), reverse=True)
        except Exception as e:
            print(f"Error sorting draft messages in refresh: {e}")
            enhanced_draft_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        categorized_mails["Drafts"] = enhanced_draft_messages
        
        return jsonify({
            'success': True,
            'categorized_mails': categorized_mails,
            'timestamp': str(datetime.now()),
            'total_messages': len(messages)
        })
        
    except Exception as e:
        print(f"Error refreshing emails: {e}")
        return jsonify({'error': 'Failed to refresh emails'}), 500

# Debug route to check session
@app.route("/debug/session")
def debug_session():
    return jsonify({
        "session_data": dict(session),
        "user_email": session.get('user_email'),
        "accounts": session.get('accounts', []),
        "session_keys": list(session.keys())
    })

# API endpoint to fetch all users for auto-complete
@app.route("/api/users")
def get_users():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        print(f"Fetching users for auto-complete. Current user: {current_email}")
        # Fetch all users from Firebase
        users_ref = firebase.ref.child("users").get() or {}
        users = []
        
        for email_key, user_data in users_ref.items():
            if user_data:
                # Convert Firebase key back to email
                email = email_key.replace(",", ".")
                
                # Create user name from first and last name
                first_name = user_data.get('first_name', '').strip()
                last_name = user_data.get('last_name', '').strip()
                name = f"{first_name} {last_name}".strip()
                
                # Fallback to email prefix if no name
                if not name:
                    name = email.split('@')[0].replace('.', ' ').title()
                
                users.append({
                    'email': email,
                    'name': name,
                    'first_name': first_name,
                    'last_name': last_name
                })
        
        print(f"Returning {len(users)} users for auto-complete")
        return jsonify(users)
        
    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to fetch users'}), 500

# API endpoint to delete emails
@app.route("/api/delete-emails", methods=["POST"])
def delete_emails():
    current_email = session.get('user_email')
    if not current_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Validate CSRF token
    csrf_token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    try:
        data = request.get_json()
        if not data or 'email_ids' not in data:
            return jsonify({'error': 'No email IDs provided'}), 400
        
        email_ids = data['email_ids']
        user_key = current_email.replace(".", ",")
        deleted_count = 0
        
        # Delete from inbox
        inbox_ref = firebase.ref.child("inbox").child(user_key)
        for email_id in email_ids:
            try:
                inbox_ref.child(email_id).delete()
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting email {email_id} from inbox: {e}")
        
        # Delete from sent
        sent_ref = firebase.ref.child("sent").child(user_key)
        for email_id in email_ids:
            try:
                sent_ref.child(email_id).delete()
            except Exception as e:
                print(f"Error deleting email {email_id} from sent: {e}")
        
        # Delete from drafts
        drafts_ref = firebase.ref.child("drafts").child(user_key)
        for email_id in email_ids:
            try:
                drafts_ref.child(email_id).delete()
            except Exception as e:
                print(f"Error deleting email {email_id} from drafts: {e}")
        
        print(f"Deleted {deleted_count} emails for user {current_email}")
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} emails'
        })
        
    except Exception as e:
        print(f"Error deleting emails: {e}")
        return jsonify({'error': 'Failed to delete emails'}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
