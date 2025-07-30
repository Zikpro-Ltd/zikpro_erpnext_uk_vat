__version__ = "0.0.1"

import frappe
from frappe.twofactor import confirm_otp_token as original_confirm_otp_token

def _patched_confirm_otp_token(login_manager):
    """Wrapper function for OTP verification with tracking"""
    # Call original function first
    result = original_confirm_otp_token(login_manager)
    
    # Custom tracking logic
    if result and login_manager.user and login_manager.user != "Guest":
        frappe.db.set_value("User", login_manager.user, "last_2fa_login", frappe.utils.now_datetime())
        frappe.db.commit()
    
    return result

def _patch_otp_verification():
    """Patch the OTP verification process"""
    # Only patch if not already patched
    if frappe.twofactor.confirm_otp_token == original_confirm_otp_token:
        frappe.twofactor.confirm_otp_token = _patched_confirm_otp_token

# Apply patch when app loads
_patch_otp_verification()