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

import frappe
from frappe.utils import now_datetime
from frappe.twofactor import confirm_otp_token as original_confirm_otp_token


def update_mfa_timestamp(user):
    try:
        if not user or user == "Guest":
            frappe.log_error("DEBUG", "Skipped MFA update: Guest user")
            return

        frappe.log_error("DEBUG", f"Updating MFA timestamp for {user}")

        if frappe.db.exists("User MFA Timestamp", {"user": user}):
            frappe.db.set_value(
                "User MFA Timestamp",
                {"user": user},
                "last_login",
                now_datetime(),
                update_modified=False
            )
        else:
            frappe.get_doc({
                "doctype": "User MFA Timestamp",
                "user": user,
                "last_login": now_datetime()
            }).insert(ignore_permissions=True)

        frappe.db.commit()
        frappe.log_error("DEBUG", f"MFA timestamp updated for {user}")

    except Exception as e:
        frappe.log_error("MFA Timestamp Update Failed", str(e))


def patched_confirm_otp_token(login_manager):
    frappe.log_error("DEBUG", f"patched_confirm_otp_token executed for {login_manager.user}")
    result = original_confirm_otp_token(login_manager)
    frappe.log_error("DEBUG", f"OTP verification result: {result}")

    if result:
        update_mfa_timestamp(login_manager.user)

    return result


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

