__version__ = "0.0.1"

import frappe
from frappe.twofactor import confirm_otp_token as original_confirm_otp_token

def update_last_2fa(user):
    """Update last 2FA login timestamp"""
    if not user or user == "Guest":
        return
    
    if frappe.db.exists("User MFA Timestamp", {"user": user}):
        frappe.db.set_value(
            "User MFA Timestamp",  # Changed
            {"user": user}, 
            "last_login", 
            frappe.utils.now_datetime()
        )
    else:
        frappe.get_doc({
            "doctype": "User MFA Timestamp",  # Changed
            "user": user,
            "last_login": frappe.utils.now_datetime()
        }).insert(ignore_permissions=True)
    
    frappe.db.commit()

def patched_confirm_otp_token(login_manager):
    """Wrapped OTP verification with tracking"""
    result = original_confirm_otp_token(login_manager)
    if result:
        update_last_2fa(login_manager.user)
    return result

# Apply monkey patch
frappe.twofactor.confirm_otp_token = patched_confirm_otp_token

# import frappe
# from frappe.twofactor import confirm_otp_token as original_confirm_otp_token

# def update_last_2fa(user):
#     """Update last 2FA login timestamp"""
#     if not user or user == "Guest":
#         return
    
#     if frappe.db.exists("Last 2FA Login", {"user": user}):
#         frappe.db.set_value(
#             "Last 2FA Login", 
#             {"user": user}, 
#             "last_login", 
#             frappe.utils.now_datetime()
#         )
#     else:
#         frappe.get_doc({
#             "doctype": "Last 2FA Login",
#             "user": user,
#             "last_login": frappe.utils.now_datetime()
#         }).insert(ignore_permissions=True)
    
#     frappe.db.commit()

# def patched_confirm_otp_token(login_manager):
#     """Wrapped OTP verification with tracking"""
#     result = original_confirm_otp_token(login_manager)
#     if result:
#         update_last_2fa(login_manager.user)
#     return result

# # Apply monkey patch
# frappe.twofactor.confirm_otp_token = patched_confirm_otp_token

# import frappe
# from frappe.twofactor import confirm_otp_token as original_confirm_otp_token

# def _patched_confirm_otp_token(login_manager):
#     """Wrapper function for OTP verification with tracking"""
#     # Call original function first
#     result = original_confirm_otp_token(login_manager)
    
#     # Custom tracking logic
#     if result and login_manager.user and login_manager.user != "Guest":
#         frappe.db.set_value("User", login_manager.user, "last_2fa_login", frappe.utils.now_datetime())
#         frappe.db.commit()
    
#     return result

# def _patch_otp_verification():
#     """Patch the OTP verification process"""
#     # Only patch if not already patched
#     if frappe.twofactor.confirm_otp_token == original_confirm_otp_token:
#         frappe.twofactor.confirm_otp_token = _patched_confirm_otp_token

# # Apply patch when app loads
# _patch_otp_verification()