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
    """Guaranteed single-user timestamp update"""
    try:
        if not user or user == "Guest":
            return

        timestamp = frappe.utils.now_datetime()
        
        # 1. Check if record exists first
        exists = frappe.db.exists("User MFA Timestamp", {"user": user})
        
        # 2. Targeted update/insert
        if exists:
            frappe.db.sql("""
                UPDATE `tabUser MFA Timestamp`
                SET last_login = %s,
                    modified = %s
                WHERE user = %s
            """, (timestamp, timestamp, user))
        else:
            frappe.db.sql("""
                INSERT INTO `tabUser MFA Timestamp`
                (name, user, last_login, creation, modified)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                frappe.generate_hash(length=10),
                user,
                timestamp,
                timestamp,
                timestamp
            ))
        
        # 3. Verify update
        updated_time = frappe.db.sql("""
            SELECT last_login FROM `tabUser MFA Timestamp`
            WHERE user = %s
        """, (user,))[0][0]
        
        if updated_time != timestamp:
            raise ValueError(f"Update failed for {user}")
            
        frappe.db.commit()
        
        # 4. Targeted cache clearance
        frappe.clear_cache(doctype="User MFA Timestamp", user=user)
        publish_realtime('mfa_updated', {'user': user})

    except Exception as e:
        frappe.log_error(
            title="MFA Update Failed",
            message=f"User: {user}\nError: {str(e)}\nQuery: {frappe.db.last_query}",
            reference_doctype="User MFA Timestamp"
        )
        raise
        
def patched_confirm_otp_token(login_manager):
    """Cluster-safe patch"""
    try:
        result = original_confirm_otp_token(login_manager)
        
        if result and login_manager.user:
            user = login_manager.user
            
            # Immediate synchronous update
            update_mfa_timestamp(user)
            
            # Async verification
            frappe.enqueue(
                'zikpro_erpnext_uk_vat.utils.verify_mfa_update',
                user=user,
                enqueue_after_commit=True,
                now=True,
                at_front=True
            )
            
        return result
        
    except Exception as e:
        frappe.log_error("OTP Verification Error", str(e))
        raise

def verify_mfa_update(user):
    """Double-checks the update persisted"""
    try:
        current = frappe.get_value(
            "User MFA Timestamp", 
            {"user": user}, 
            "last_login"
        )
        
        if not current or current < frappe.utils.add_to_date(None, minutes=-1):
            update_mfa_timestamp(user)
            
    except Exception as e:
        frappe.log_error("MFA Verification Failed", str(e))

def patch_twofactor():
    """Safe initialization"""
    from frappe import twofactor
    if not hasattr(twofactor, '_original_confirm_otp_token'):
        twofactor._original_confirm_otp_token = twofactor.confirm_otp_token
        twofactor.confirm_otp_token = patched_confirm_otp_token

        # publish_realtime('reload_twofactor_patch')

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

# def clear_cache_handler(data):
#     """Forces cache clearance across workers"""
#     frappe.clear_cache(doctype="User MFA Timestamp")
#     frappe.db.commit()

def clear_user_cache(data):
    """Clears cache for specific user"""
    frappe.clear_cache(doctype="User MFA Timestamp", user=data['user'])
    frappe.db.commit()