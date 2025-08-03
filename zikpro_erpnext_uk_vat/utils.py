import frappe
import time
from datetime import datetime
from frappe.utils import now_datetime,add_to_date
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

def log_debug(message, user=None):
    """Creates Error Log entries matching your doctype structure"""
    try:
        # Prepare the error data
        error_data = {
            "doctype": "Error Log",
            "title": "MFA Debug"[:140],  # Truncate to match title field
            "error": f"""Traceback (most recent call last):
  File "zikpro_erpnext_uk_vat/utils.py", line 1, in debug_logger
    DEBUG MESSAGE
{message}""",  # Formatted to match error traceback style
            "seen": 0,
            "reference_doctype": "User MFA Timestamp",
            "reference_name": user or "System"
        }

        # Create the error log with retry logic
        for attempt in range(3):
            try:
                frappe.get_doc(error_data).insert(ignore_permissions=True)
                frappe.db.commit()
                break
            except Exception:
                if attempt == 2:
                    raise
                frappe.db.rollback()
                frappe.sleep(0.5)
                
    except Exception as e:
        # Fallback to console if Error Log fails
        print(f"DEBUG LOG FAILED: {str(e)}\nOriginal message: {message}")

def update_mfa_timestamp(user):
    """Updates timestamp with perfect Error Log formatting"""
    try:
        # Start transaction
        frappe.db.begin()
        
        # Log start marker
        log_debug("="*50 + "\nSTART update_mfa_timestamp\n" + "="*50, user)
        
        if not user or user == "Guest":
            log_debug("Skipping Guest/empty user", user)
            return

        # Get current timestamp
        timestamp = frappe.utils.now_datetime()
        log_debug(f"Timestamp: {timestamp}\nUser: {user}", user)
        
        # Update logic
        if frappe.db.exists("User MFA Timestamp", {"user": user}):
            frappe.db.set_value(
                "User MFA Timestamp",
                {"user": user},
                "last_login",
                timestamp
            )
            log_debug("Updated existing record", user)
        else:
            doc = frappe.get_doc({
                "doctype": "User MFA Timestamp",
                "user": user,
                "last_login": timestamp
            }).insert(ignore_permissions=True)
            log_debug(f"Created new record: {doc.name}", user)
        
        frappe.db.commit()
        log_debug("Update completed successfully", user)
        
    except Exception as e:
        frappe.db.rollback()
        # Format error to match your Error Log style
        error_msg = f"""Traceback (most recent call last):
  File "zikpro_erpnext_uk_vat/utils.py", line 1, in update_mfa_timestamp
    ERROR DETAILS
{str(e)}"""
        log_debug(error_msg, user)
    finally:
        log_debug("="*50 + "\nEND update_mfa_timestamp\n" + "="*50, user)

def patched_confirm_otp_token(login_manager):
    """Modified OTP verification with proper Error Log integration"""
    try:
        # Start debug trace
        log_debug("="*50 + "\nSTART patched_confirm_otp_token\n" + "="*50, 
                 getattr(login_manager, 'user', None))
        
        log_debug("Calling original OTP verification", login_manager.user)
        result = original_confirm_otp_token(login_manager)
        log_debug(f"OTP verification result: {result}", login_manager.user)
        
        if result and login_manager.user:
            user = login_manager.user
            log_debug("Initiating MFA timestamp update", user)
            
            # Immediate synchronous update
            update_mfa_timestamp(user)
            
            # Async verification as backup
            log_debug("Enqueuing async verification", user)
            frappe.enqueue(
                'zikpro_erpnext_uk_vat.utils.verify_mfa_update',
                user=user,
                enqueue_after_commit=True,
                now=True
            )
            
        return result
        
    except Exception as e:
        error_msg = f"""Traceback (most recent call last):
  File "zikpro_erpnext_uk_vat/utils.py", line 1, in patched_confirm_otp_token
    OTP VERIFICATION ERROR
{str(e)}"""
        log_debug(error_msg, getattr(login_manager, 'user', None))
        raise
    finally:
        log_debug("="*50 + "\nEND patched_confirm_otp_token\n" + "="*50,
                getattr(login_manager, 'user', None))

def verify_mfa_update(user):
    """Verification with Error Log formatted output"""
    try:
        log_debug("="*50 + "\nSTART verify_mfa_update\n" + "="*50, user)
        start_time = time.time()
        
        log_debug("Fetching current timestamp from DB", user)
        current = frappe.get_value(
            "User MFA Timestamp", 
            {"user": user}, 
            "last_login"
        )
        log_debug(f"Current timestamp: {current}", user)
        
        if not current or current < frappe.utils.add_to_date(None, minutes=-1):
            log_debug("Timestamp missing/stale - triggering update", user)
            update_mfa_timestamp(user)
        else:
            log_debug("Timestamp is current - no update needed", user)
            
    except Exception as e:
        error_msg = f"""Traceback (most recent call last):
  File "zikpro_erpnext_uk_vat/utils.py", line 1, in verify_mfa_update
    VERIFICATION ERROR
{str(e)}"""
        log_debug(error_msg, user)
    finally:
        duration = time.time() - start_time
        log_debug(f"Completed in {duration:.2f} seconds", user)
        log_debug("="*50 + "\nEND verify_mfa_update\n" + "="*50, user)

# def update_mfa_timestamp(user):
#     """Guaranteed single-user timestamp update"""
#     log_debug("Entered update_mfa_timestamp", user)
    
#     try:
#         if not user or user == "Guest":
#             log_debug("Skipping Guest/empty user", user)
#             return

#         timestamp = now_datetime()
#         log_debug(f"Preparing timestamp update: {timestamp}", user)
        
#         # 1. STRICT user-specific update
#         log_debug("Attempting direct SQL update", user)
#         update_result = frappe.db.sql("""
#             UPDATE `tabUser MFA Timestamp`
#             SET last_login = %s,
#                 modified = %s
#             WHERE user = %s
#         """, (timestamp, timestamp, user))
        
#         affected_rows = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
#         log_debug(f"Update affected {affected_rows} rows", user)
        
#         # 2. Insert if record doesn't exist
#         if affected_rows == 0:
#             log_debug("No existing record found, attempting insert", user)
#             name = frappe.generate_hash(length=10)
#             frappe.db.sql("""
#                 INSERT INTO `tabUser MFA Timestamp`
#                 (name, user, last_login, creation, modified)
#                 VALUES (%s, %s, %s, %s, %s)
#             """, (name, user, timestamp, timestamp, timestamp))
#             log_debug(f"Inserted new record with name: {name}", user)
        
#         # 3. Verify ONLY this user was updated
#         log_debug("Verifying update", user)
#         updated_user = frappe.db.sql("""
#             SELECT user FROM `tabUser MFA Timestamp`
#             WHERE last_login = %s
#             ORDER BY modified DESC LIMIT 1
#         """, (timestamp,))
        
#         if not updated_user:
#             log_debug("WARNING: No user found with updated timestamp", user)
#         elif updated_user[0][0] != user:
#             error_msg = f"Wrong user updated! Expected {user}, got {updated_user[0][0]}"
#             log_debug(error_msg, user)
#             raise ValueError(error_msg)
#         else:
#             log_debug("Verified correct user update", user)
        
#         frappe.db.commit()
#         log_debug("Changes committed to database", user)
        
#         # 4. Force cache refresh
#         log_debug("Clearing cache for user", user)
#         frappe.clear_cache(doctype="User MFA Timestamp", user=user)
#         publish_realtime('user_mfa_updated', {'user': user})
#         log_debug("Cache cleared and realtime event published", user)

#     except Exception as e:
#         error_msg = f"Exception in update_mfa_timestamp: {str(e)}"
#         log_debug(error_msg, user)
#         frappe.log_error(
#             title="MFA Update Failed",
#             message=f"User: {user}\nError: {str(e)}\nSQL: {frappe.db.last_query}",
#             reference_doctype="User MFA Timestamp"
#         )
#         raise
        
# def patched_confirm_otp_token(login_manager):
#     """Worker-safe patch with verification"""
#     log_debug("Entered patched_confirm_otp_token", getattr(login_manager, 'user', None))
    
#     try:
#         log_debug("Calling original confirm_otp_token")
#         result = original_confirm_otp_token(login_manager)
#         log_debug(f"Original confirm_otp_token returned: {result}")
        
#         if result and login_manager.user:
#             user = login_manager.user
#             log_debug(f"OTP confirmed for user: {user}", user)
            
#             # Immediate update
#             log_debug("Starting immediate timestamp update", user)
#             update_mfa_timestamp(user)
            
#             # Async backup verification
#             log_debug("Enqueuing async verification", user)
#             frappe.enqueue(
#                 'zikpro_erpnext_uk_vat.utils.verify_mfa_update',
#                 user=user,
#                 enqueue_after_commit=True,
#                 now=True,
#                 at_front=True
#             )
            
#         return result
        
#     except Exception as e:
#         error_msg = f"Exception in patched_confirm_otp_token: {str(e)}"
#         log_debug(error_msg, getattr(login_manager, 'user', None))
#         frappe.log_error("OTP Patch Error", str(e))
#         raise

# def verify_mfa_update(user):
#     """Ensures update persisted across all workers"""
#     log_debug("Entered verify_mfa_update", user)
#     start_time = time.time()
    
#     try:
#         log_debug("Fetching current timestamp from DB", user)
#         current = frappe.get_value(
#             "User MFA Timestamp", 
#             {"user": user}, 
#             "last_login"
#         )
#         log_debug(f"Current DB timestamp: {current}", user)
        
#         if not current or current < add_to_date(None, minutes=-1):
#             log_debug("Timestamp missing or stale, triggering update", user)
#             update_mfa_timestamp(user)
#         else:
#             log_debug("Timestamp is current, no update needed", user)
            
#     except Exception as e:
#         error_msg = f"Exception in verify_mfa_update: {str(e)}"
#         log_debug(error_msg, user)
#         frappe.log_error("MFA Verification Failed", str(e))
    
#     duration = time.time() - start_time
#     log_debug(f"verify_mfa_update completed in {duration:.2f}s", user)

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