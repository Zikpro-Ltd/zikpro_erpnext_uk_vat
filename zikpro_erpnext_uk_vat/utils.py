import frappe
import time
from datetime import datetime
from frappe.utils import now_datetime
from frappe.twofactor import confirm_otp_token as original_confirm_otp_token

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


# MFA Timestamp Functions
# def update_mfa_timestamp(user):
#     """Update the MFA timestamp for the given user"""
#     try:
#         if not user or user == "Guest":
#             return

#         # Using direct SQL for better performance in both local and cloud
#         if frappe.db.exists("User MFA Timestamp", {"user": user}):
#             frappe.db.sql("""
#                 UPDATE `tabUser MFA Timestamp`
#                 SET last_login = %s
#                 WHERE user = %s
#             """, (now_datetime(), user))
#         else:
#             frappe.get_doc({
#                 "doctype": "User MFA Timestamp",
#                 "user": user,
#                 "last_login": now_datetime()
#             }).insert(ignore_permissions=True, ignore_if_duplicate=True)

#         frappe.db.commit()  # Explicit commit for immediate update

#     except Exception as e:
#         frappe.log_error(title="MFA Timestamp Update Failed", message=str(e))
#         frappe.db.rollback()

def update_mfa_timestamp(user):
    try:
        if not user or user == "Guest":
            return

        # Bypass ALL permission checks (even in production)
        frappe.flags.ignore_permissions = True  # ← Global override

        if frappe.db.exists("User MFA Timestamp", {"user": user}):
            frappe.db.set_value(
                "User MFA Timestamp",
                {"user": user},
                "last_login",
                now_datetime(),
                update_modified=False
            )
        else:
            doc = frappe.get_doc({
                "doctype": "User MFA Timestamp",
                "user": user,
                "last_login": now_datetime()
            })
            doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(
            title="MFA Timestamp Failed",
            message=f"User: {user}\nError: {str(e)}",
            reference_doctype="User MFA Timestamp"
        )
    finally:
        frappe.flags.ignore_permissions = False  # ← Reset

def patched_confirm_otp_token(login_manager):
    """Wrapper around the original OTP confirmation that records successful MFA"""
    result = original_confirm_otp_token(login_manager)
    
    if result:
        update_mfa_timestamp(login_manager.user)
    
    return result

def patch_twofactor():
    """Apply the monkey-patch to Frappe's twofactor functions"""
    from frappe import twofactor
    if twofactor.confirm_otp_token.__module__ != __name__:
        twofactor.confirm_otp_token = patched_confirm_otp_token
        frappe.log_error("MFA Patch", "Successfully patched confirm_otp_token")

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

        # ✅ 2) Update MFA timestamp
        # if frappe.session.data.get("otp_verified"):
        #     update_mfa_timestamp(login_manager.user)

    except Exception:
        frappe.log_error("on_login_handler Error", frappe.get_traceback())

