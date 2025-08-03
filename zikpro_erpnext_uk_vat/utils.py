import frappe
import time
from datetime import datetime
from frappe.utils import now_datetime,add_to_date,get_traceback
from frappe.twofactor import confirm_otp_token as original_confirm_otp_token
from frappe import publish_realtime

@frappe.whitelist(allow_guest=False)
def update_client_info(screen_width, screen_height, color_depth, pixel_ratio, timezone_offset):
    """Store real-time client information in session"""
    try:
        frappe.session.data.update({
            'client_info': {
                'width': max(1, int(screen_width)),
                'height': max(1, int(screen_height)),
                'color_depth': max(8, int(color_depth)),
                'scaling': max(0.5, float(pixel_ratio)),
                'timezone_offset': float(timezone_offset),
                'last_updated': datetime.now().isoformat()
            }
        })
        return {"success": True}
    except Exception as e:
        frappe.log_error("Client Info Update Failed", str(e))
        return {"success": False}

# def on_login_handler(login_manager):
#     """Handles login-related tasks: set default client info + store last 2FA login."""
#     try:
#         # 1️⃣ Set default client info
#         set_default_client_info()

#         frappe.log_error("DEBUG", f"on_login_handler executed for {frappe.session.user}")

#     except Exception:
#         frappe.log_error("on_login_handler Error", frappe.get_traceback())

def set_default_client_info(doc, method):
    """Set default values if client info not available"""
    if not frappe.session.data.get('client_info'):
        frappe.session.data['client_info'] = {
            'width': 1921,
            'height': 1081,
            'color_depth': 25,
            'scaling': 1,
            'timezone_offset': -time.timezone // 3600,
            'is_fallback': True
        }

def get_client_info():
    """Retrieve stored client information"""
    return frappe.session.data.get('client_info', {})

def log_mfa_error(user, title, error_message):
    """Forcefully create an Error Log entry for MFA failures"""
    try:
        frappe.get_doc({
            "doctype": "Error Log",
            "title": title,
            "error": error_message,
            "method": "MFA Update",
            "reference_doctype": "User MFA Timestamp",
            "reference_name": user if user else "Unknown User"
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        # If Error Log insertion itself fails, write to site logs
        print(f"Failed to log MFA error: {str(e)}\nOriginal Error: {error_message}")


def update_mfa_timestamp(user):
    try:
        if not user or user == "Guest":
            return

        timestamp = now_datetime()

        update_result = frappe.db.sql("""
            UPDATE `tabUser MFA Timestamp`
            SET last_login = %s, modified = %s
            WHERE user = %s
        """, (timestamp, timestamp, user))

        affected_rows = frappe.db.affected_rows()

        if affected_rows == 0:
            name = frappe.generate_hash(length=10)
            frappe.db.sql("""
                INSERT INTO `tabUser MFA Timestamp`
                (name, user, last_login, creation, modified)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, user, timestamp, timestamp, timestamp))

        frappe.db.commit()

        frappe.clear_cache(doctype="User MFA Timestamp")
        frappe.clear_cache(user=user)

        publish_realtime('user_mfa_updated', {'user': user})
        publish_realtime('mfa_updated', {'user': user, 'timestamp': timestamp})

    except Exception:
        error_msg = f"User: {user}\nError: {get_traceback()}\nSQL: {frappe.db.last_query}"
        frappe.log_error(title="MFA Update Failed", message=error_msg, reference_doctype="User MFA Timestamp")
        log_mfa_error(user, "MFA Update Failed", error_msg)  # ✅ Always log to Error Log
        raise


# def patched_confirm_otp_token(login_manager):
#     try:
#         result = frappe.twofactor._original_confirm_otp_token(login_manager)

#         if result and login_manager.user:
#             user = login_manager.user
#             update_mfa_timestamp(user)

#             frappe.enqueue(
#                 "zikpro_erpnext_uk_vat.utils.verify_mfa_update",
#                 user=user,
#                 enqueue_after_commit=True,
#                 now=True,
#                 at_front=True
#             )

#         return result

#     except Exception:
#         error_msg = get_traceback()
#         frappe.log_error("OTP Patch Error", error_msg)
#         log_mfa_error(login_manager.user if login_manager else "Unknown", "OTP Patch Error", error_msg)  # ✅ Always log
#         raise


def verify_mfa_update(user):
    try:
        frappe.log_error("DEBUG", f"verify_mfa_update executed for user {user}")
        timestamp = now_datetime()
        current = frappe.get_value("User MFA Timestamp", {"user": user}, "last_login")

        if not current or current < add_to_date(None, minutes=-1):
            update_mfa_timestamp(user)

        frappe.db.commit()
        frappe.clear_cache(doctype="User MFA Timestamp")
        frappe.clear_cache(user=user)

        publish_realtime('mfa_updated', {'user': user, 'timestamp': timestamp})

    except Exception:
        error_msg = f"User: {user}\nError: {get_traceback()}\nSQL: {frappe.db.last_query}"
        frappe.log_error(title="MFA Verify Update Failed", message=error_msg, reference_doctype="User MFA Timestamp")
        log_mfa_error(user, "MFA Verify Update Failed", error_msg)
        raise


# def patch_twofactor():
#     from frappe import twofactor
#     frappe.log_error("DEBUG", "patch_twofactor called!")
#     if not hasattr(twofactor, "_original_confirm_otp_token"):
#         frappe.log_error("DEBUG", "patch_twofactor applied successfully!")
#         twofactor._original_confirm_otp_token = twofactor.confirm_otp_token
#         twofactor.confirm_otp_token = patched_confirm_otp_token
#     else:
#         frappe.log_error("DEBUG", "patch_twofactor already applied!")

def patch_twofactor():
    try:
        from frappe import twofactor

        if not hasattr(twofactor, "_original_confirm_otp_token"):
            twofactor._original_confirm_otp_token = twofactor.confirm_otp_token
            twofactor.confirm_otp_token = twofactor._original_confirm_otp_token
            print("✅ MFA Patch Applied")
        else:
            print("⚠️ MFA Patch Already Applied")

    except Exception:
        print("❌ MFA Patch Error:", get_traceback())

# def create_initial_records():
#     users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
#     for user in users:
#         update_mfa_timestamp(user)

def create_initial_records():
    """Create MFA timestamp records only for users that don't already exist."""
    try:
        # Get all enabled users
        users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")

        for user in users:
            exists = frappe.db.exists("User MFA Timestamp", {"user": user})
            if not exists:  # Only create if record does not exist
                update_mfa_timestamp(user)

        frappe.db.commit()

    except Exception:
        error_msg = f"Error creating initial MFA records:\n{frappe.get_traceback()}"
        frappe.log_error(title="MFA Initial Record Creation Failed", message=error_msg)
        log_mfa_error("SYSTEM", "MFA Initial Record Creation Failed", error_msg)


def clear_user_cache(data):
    frappe.clear_cache(doctype="User MFA Timestamp")
    frappe.clear_cache(user=data["user"])
    frappe.db.commit()



def on_login_handler(login_manager):
    """Handles login-related tasks: store client info + MFA timestamp."""
    try:
        # ✅ 1) Set default client info
        set_default_client_info()

    except Exception:
        frappe.log_error("on_login_handler Error", frappe.get_traceback())

# def on_login_handler(login_manager):
#     try:
#         # Existing logic
#         set_default_client_info()

#         # Ensure patch is applied (safe call)
#         patch_twofactor()

#         # ✅ NEW: Update MFA timestamp if MFA is enabled
#         is_mfa_enabled = frappe.db.get_value("User", login_manager.user, "mfa_enabled")
#         frappe.log_error("DEBUG", f"Login for {login_manager.user}, MFA Enabled={is_mfa_enabled}")

#         if is_mfa_enabled:
#             update_mfa_timestamp(login_manager.user)

#     except Exception:
#         frappe.log_error("on_login_handler Error", get_traceback())


# def clear_cache_handler(data):
#     """Forces cache clearance across workers"""
#     frappe.clear_cache(doctype="User MFA Timestamp")
#     frappe.db.commit()

@frappe.whitelist(allow_guest=True)
def custom_login():
    from frappe.auth import LoginManager

    login_manager = LoginManager()
    login_manager.authenticate()
    login_manager.post_login()

    frappe.log_error("DEBUG", f"Custom Login executed for {login_manager.user}")

    if login_manager.user and frappe.db.get_value("User", login_manager.user, "mfa_enabled"):
        frappe.log_error("DEBUG", f"✅ MFA Enabled for {login_manager.user}, updating timestamp")
        update_mfa_timestamp(login_manager.user)
    else:
        frappe.log_error("DEBUG", f"❌ MFA Disabled for {login_manager.user}, skipping update")

    frappe.local.response["message"] = "Logged In"

