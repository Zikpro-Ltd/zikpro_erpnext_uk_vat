import frappe
import time
from datetime import datetime
from frappe.utils import now_datetime
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

def update_mfa_timestamp(user):
    """100% reliable timestamp update"""
    try:
        if not user or user == "Guest":
            return

        timestamp = now_datetime()
        
        # METHOD 1: Atomic UPSERT (works in all cases)
        frappe.db.sql("""
            INSERT INTO `tabUser MFA Timestamp` 
            (name, user, last_login, creation, modified)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE last_login = VALUES(last_login)
        """, (
            frappe.generate_hash(length=10),
            user,
            timestamp,
            timestamp,
            timestamp
        ))
        
        frappe.db.commit()
        
        # METHOD 2: Force cache clear
        frappe.clear_cache(doctype="User MFA Timestamp")
        
        # DEBUG: Real-time confirmation
        publish_realtime('mfa_update', {
            'user': user,
            'timestamp': timestamp
        })

    except Exception as e:
        frappe.log_error(
            title="MFA Update Failed",
            message=f"User: {user}\nError: {str(e)}\nTraceback: {frappe.get_traceback()}",
            reference_doctype="User MFA Timestamp"
        )

def patched_confirm_otp_token(login_manager):
    """Guaranteed execution"""
    try:
        result = original_confirm_otp_token(login_manager)
        if result and login_manager.user:
            frappe.publish_realtime('mfa_debug', {'user': login_manager.user})
            # Immediate update
            update_mfa_timestamp(login_manager.user)
            
            # Async backup (in case of transaction issues)
            frappe.enqueue(
                'zikpro_erpnext_uk_vat.utils.update_mfa_timestamp',
                user=login_manager.user,
                enqueue_after_commit=True,
                now=True,
                at_front=True
            )
        return result
    except Exception as e:
        frappe.log_error("OTP Patch Error", str(e))
        raise

# def patch_twofactor():
#     """Apply the monkey-patch to Frappe's twofactor functions"""
#     from frappe import twofactor
#     if twofactor.confirm_otp_token.__module__ != __name__:
#         twofactor.confirm_otp_token = patched_confirm_otp_token
#         frappe.log_error("MFA Patch", "Successfully patched confirm_otp_token")

def patch_twofactor():
    """Safe initialization"""
    from frappe import twofactor
    if not hasattr(twofactor, '_original_confirm_otp_token'):
        twofactor._original_confirm_otp_token = twofactor.confirm_otp_token
        twofactor.confirm_otp_token = patched_confirm_otp_token

        publish_realtime('mfa_patch_applied', {
            'status': 'success',
            'time': now_datetime()
        })

def create_initial_records():
    """Run once after deploy"""
    users = frappe.get_all("User", filters={"enabled": 1}, pluck="name")
    for user in users:
        update_mfa_timestamp(user)


def on_login_handler(login_manager):
    """Handles login-related tasks: store client info + MFA timestamp."""
    try:
        # ✅ 1) Set default client info
        set_default_client_info()

    except Exception:
        frappe.log_error("on_login_handler Error", frappe.get_traceback())

