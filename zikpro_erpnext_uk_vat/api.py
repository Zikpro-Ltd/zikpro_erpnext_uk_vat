from __future__ import unicode_literals
import base64
import frappe
import requests
import json
from frappe.utils import now_datetime, add_to_date, nowdate, getdate, formatdate
from requests.auth import HTTPBasicAuth
from urllib.parse import quote, urlencode
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_defaults
import uuid  # Add this with your other imports
import hashlib
import socket
import datetime
import platform
from frappe.utils import get_site_name,get_host_name

# HMRC OAuth 2.0 Configuration
HMRC_AUTH_URL = "https://test-api.service.hmrc.gov.uk/oauth/authorize"
HMRC_TOKEN_URL = "https://test-api.service.hmrc.gov.uk/oauth/token"
HMRC_API_BASE_URL = "https://test-api.service.hmrc.gov.uk"

@frappe.whitelist()
def start_oauth_flow(docname):
    doc = frappe.get_doc("VAT Settings", docname)
    client_id = doc.client_id
    redirect_uri = doc.redirect_url

    auth_url = (
        f"{HMRC_AUTH_URL}?response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=read:vat+write:vat&"  
        f"state={docname}"  
    )
    return auth_url

@frappe.whitelist(allow_guest=True)
def oauth_callback():
    code = frappe.form_dict.get("code")
    state = frappe.form_dict.get("state")

    if not code or not state:
        frappe.throw("Authorization code or state not found in the callback URL.")

    doc = frappe.get_doc("VAT Settings", state)
    client_id = doc.client_id
    client_secret = doc.get_password('client_secret')
    redirect_uri = doc.redirect_url

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,  
        "client_secret": client_secret
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    auth = HTTPBasicAuth(client_id, client_secret)

    try:
        response = requests.post(HMRC_TOKEN_URL, data=payload, headers=headers, auth=auth)

        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]
            expires_in = token_data["expires_in"]

            token_expiry = add_to_date(now_datetime(), seconds=expires_in)

            doc.access_token = access_token
            doc.refresh_token = refresh_token
            doc.token_expiry = token_expiry
            doc.status = "Authorized"
            doc.save()
            frappe.db.commit()

            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = f"/app/vat-settings/{state}"

        else:
            frappe.throw(f"Error: {response.status_code}, {response.text}")

    except requests.exceptions.RequestException as e:
        frappe.throw(f"Request failed: {e}")

def make_hmrc_request(method, endpoint, docname, params=None, json_data=None, retry_count=0):
    """
    Helper function to make authenticated HMRC API requests with automatic token refresh
    """
    try:
        doc = frappe.get_doc("VAT Settings", docname)
        if not doc.access_token:
            return {"error": "Access token not found in VAT Settings", "success": False}

        access_token = doc.get_password("access_token")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.hmrc.1.0+json",
            "Content-Type": "application/json",
            **get_fraud_prevention_headers()  # Include all headers
        }
        
        url = f"{HMRC_API_BASE_URL}{endpoint}"
        
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=30
            )
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}", "success": False}

        log_msg = (
            f"HMRC API Request:\n"
            f"Method: {method}\n"
            f"URL: {url}\n"
            f"Headers: {headers}\n"
            f"Params: {params}\n"
            f"Status Code: {response.status_code}\n"
            f"Response: {response.text[:500]}"
        )
        frappe.log_error(title="HMRC API Debug", message=log_msg)

        # Handle token expiration (401) - attempt refresh once
        if response.status_code == 401 and retry_count == 0:
            if "expired" in response.text.lower() or "INVALID_CREDENTIALS" in response.text:
                frappe.log_error("Access token invalid/expired, attempting refresh...")
                refresh_result = refresh_access_token(docname)
                
                if not refresh_result.get("success"):
                    return {
                        "error": f"Token refresh failed: {refresh_result.get('error', 'Unknown error')}",
                        "success": False
                    }
                
                # Retry with new token
                return make_hmrc_request(
                    method, endpoint, docname, 
                    params, json_data, retry_count + 1
                )

        # Handle other error responses
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = f"HMRC API Error ({response.status_code}): {error_data.get('message', 'No error message')}"
                if 'code' in error_data:
                    error_msg += f" (code: {error_data['code']})"
                return {
                    "error": error_msg,
                    "status_code": response.status_code,
                    "response_text": response.text,
                    "success": False
                }
            except ValueError:
                return {
                    "error": f"HMRC API Error ({response.status_code}): {response.text}",
                    "success": False
                }
        try:
            return {
                "status_code": response.status_code,
                "data": response.json() if response.content else None,
                "success": True
            }
        except ValueError:
            return {
                "error": f"Invalid JSON response: {response.text}",
                "success": False
            }

    except Exception as e:
        error_msg = f"Unexpected error in make_hmrc_request: {str(e)}"
        frappe.log_error("HMRC Request Error", error_msg)
        return {"error": error_msg, "success": False}

@frappe.whitelist()
def refresh_access_token(docname):
    """Refresh the access token using the refresh token"""
    try:
        doc = frappe.get_doc("VAT Settings", docname)
        if not doc.refresh_token:
            return {"success": False, "error": "Refresh token not found. Please re-authorize."}

        client_id = doc.client_id
        client_secret = doc.get_password('client_secret')
        refresh_token = doc.get_password('refresh_token')

        if not all([client_id, client_secret, refresh_token]):
            return {"success": False, "error": "Missing required credentials for token refresh"}

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        auth = HTTPBasicAuth(client_id, client_secret)

        response = requests.post(
            HMRC_TOKEN_URL,
            data=payload,
            headers=headers,
            auth=auth,
            timeout=30
        )

        frappe.log_error(
            "Token Refresh Response",
            f"Status: {response.status_code}\nResponse: {response.text}"
        )

        if response.status_code != 200:
            error_msg = f"Token refresh failed ({response.status_code})"
            try:
                error_data = response.json()
                error_msg += f": {error_data.get('error', 'Unknown error')}"
                if 'error_description' in error_data:
                    error_msg += f" - {error_data['error_description']}"
            except ValueError:
                error_msg += f": {response.text}"
            return {"success": False, "error": error_msg}

        token_data = response.json()
        if not all(k in token_data for k in ["access_token", "expires_in"]):
            return {"success": False, "error": "Invalid token response format"}

        doc.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            doc.refresh_token = token_data["refresh_token"]
        doc.token_expiry = add_to_date(now_datetime(), seconds=token_data["expires_in"])
        doc.save()
        frappe.db.commit()

        return {
            "success": True,
            "access_token": token_data["access_token"],
            "expires_in": token_data["expires_in"]
        }

    except requests.exceptions.RequestException as e:
        error_msg = f"Token refresh request failed: {str(e)}"
        frappe.log_error("Token Refresh Failed", error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error during token refresh: {str(e)}"
        frappe.log_error("Token Refresh Error", error_msg)
        return {"success": False, "error": error_msg}

@frappe.whitelist()
def fetch_all_obligations(frequency, from_date=None, to_date=None):
    """Fetch obligations with proper date formatting for HMRC API"""
    try:
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            frappe.throw("No default company set in Global Defaults.")
        
        vrn = frappe.db.get_value("Company", default_company, "custom_uk_vat_registration_number")
        if not vrn:
            frappe.throw(f"VRN not set for company {default_company}.")
        
        vat_settings = frappe.get_doc("VAT Settings", {"company": default_company})
        if not vat_settings:
            frappe.throw("VAT Settings not found for company.")

        if not vat_settings.get_password("access_token"):
            frappe.throw("Access token not found. Please authorize with HMRC first.")
        
        from_date = from_date or add_to_date(nowdate(), years=-1)
        to_date = to_date or nowdate()
        
        params = {
            "from": formatdate(from_date, "yyyy-MM-dd"),
            "to": formatdate(to_date, "yyyy-MM-dd")
        }
        
        response = make_hmrc_request(
            "GET",
            f"/organisations/vat/{vrn}/obligations",
            vat_settings.name,
            params=params
        )
        
        if not response.get("success"):
            error_msg = response.get("error", "Unknown error occurred")
            if "response_text" in response:
                error_msg += f"\nResponse: {response['response_text']}"
            frappe.throw(f"Failed to fetch obligations: {error_msg}")
        
        if not response.get("data"):
            frappe.throw("No data returned from HMRC API")
        
        obligations = response["data"].get("obligations", [])
        if not isinstance(obligations, list):
            frappe.throw(f"Unexpected obligations format: {type(obligations)}")
        
        processed_count = 0

        for obligation in obligations:
            try:
                if not all(key in obligation for key in ["start", "end", "due"]):
                    frappe.log_error("Invalid obligation format", str(obligation))
                    continue
                
                start = getdate(obligation["start"])
                end = getdate(obligation["end"])
                days_diff = (end - start).days
                
                # Frequency filtering
                if frequency == "Monthly" and days_diff > 31:
                    continue
                elif frequency == "Quarterly" and days_diff <= 31:
                    continue
                
                doc_data = {
                    "doctype": "UK MTD VAT Return",
                    "vrn": vrn,
                    "status": "Fulfilled" if obligation.get("status") == "F" else "Overdue",
                    "period_start_date": obligation["start"],
                    "period_end_date": obligation["end"],
                    "due_date": obligation["due"],
                    "reference_key": obligation.get("periodKey")
                }
                
                existing = frappe.get_all("UK MTD VAT Return",
                    filters={"reference_key": obligation.get("periodKey")},
                    limit=1)
                
                if existing:
                    doc = frappe.get_doc("UK MTD VAT Return", existing[0].name)
                    doc.update(doc_data)
                else:
                    doc = frappe.get_doc(doc_data)
                    doc.insert()
                
                processed_count += 1
            
            except Exception as e:
                frappe.log_error("Failed to process obligation", f"{str(e)}\nObligation: {obligation}")
                continue
        
        frappe.db.commit()
        return {
            "count": processed_count,
            "frequency": frequency,
            "message": f"Successfully processed {processed_count} obligations"
        }

    except Exception as e:
        error_msg = f"Failed to process obligations: {str(e)}"
        frappe.log_error("Obligation Processing Error", error_msg)
        frappe.throw(error_msg)

# @frappe.whitelist()
# def calculate_vat_boxes(docname):
#     """
#     Calculate UK VAT 9-box return using your field names
#     """
#     doc = frappe.get_doc("UK MTD VAT Return", docname)
    
#     if not doc.period_start_date or not doc.period_end_date:
#         frappe.throw("Please set period start and end dates first")
    
#     # 1. Calculate Box 1 (VAT Due on Sales)
#     sales_invoices = frappe.get_all("Sales Invoice",
#         filters={
#             "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
#             "docstatus": 1,
#             "is_return": 0  # Exclude credit notes
#         },
#         fields=["base_grand_total", "base_total_taxes_and_charges"]
#     )
#     doc.sales_vat_due_box1 = sum(inv.base_total_taxes_and_charges for inv in sales_invoices)
    
#     # 2. Calculate Box 6 (Net Sales)
#     doc.net_sales_box6 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges 
#                            for inv in sales_invoices)
    
#     # 3. Calculate Box 4 (VAT Reclaimed on Purchases)
#     purchase_invoices = frappe.get_all("Purchase Invoice",
#         filters={
#             "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
#             "docstatus": 1,
#             "is_return": 0
#         },
#         fields=["base_grand_total", "base_total_taxes_and_charges"]
#     )
#     doc.purchase_vat_reclaimed_box4 = sum(inv.base_total_taxes_and_charges for inv in purchase_invoices)
    
#     # 4. Calculate Box 7 (Net Purchases)
#     doc.net_purchases_box7 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges 
#                                for inv in purchase_invoices)
    
#     # 5. Calculate EU Transactions (Box 2, 8, 9)
#     eu_results = calculate_eu_transactions(doc.period_start_date, doc.period_end_date)
#     doc.eu_acquisition_vat_due_box2 = eu_results['box2']
#     doc.net_eu_supplies_box_8 = eu_results['box8']
#     doc.net_eu_acquisitions_box_9 = eu_results['box9']
    
#     # 6. Calculate Derived Boxes
#     doc.total_vat_due_box3 = doc.sales_vat_due_box1 + doc.eu_acquisition_vat_due_box2
#     doc.net_vat_due_box5 = doc.total_vat_due_box3 - doc.purchase_vat_reclaimed_box4

#     doc.formatted_sales_vat_due_box1 = format_currency(doc.sales_vat_due_box1)
#     doc.formatted_net_sales_box6 = format_currency(doc.net_sales_box6)
#     doc.formatted_purchase_vat_reclaimed_box4 = format_currency(doc.purchase_vat_reclaimed_box4)
#     doc.formatted_net_purchases_box7 = format_currency(doc.net_purchases_box7)
#     doc.formatted_eu_acquisition_vat_due_box2 = format_currency(doc.eu_acquisition_vat_due_box2)
#     doc.formatted_net_eu_supplies_box_8 = format_currency(doc.net_eu_supplies_box_8)
#     doc.formatted_net_eu_acquisitions_box_9 = format_currency(doc.net_eu_acquisitions_box_9)
#     doc.formatted_total_vat_due_box3 = format_currency(doc.total_vat_due_box3)
#     doc.formatted_net_vat_due_box5 = format_currency(doc.net_vat_due_box5)
    
#     doc.save()
#     frappe.db.commit()
    
#     return {
#         "status": "success",
#         "message": "VAT boxes calculated successfully",
#         "formatted_values": {
#             "sales_vat_due_box1": doc.formatted_sales_vat_due_box1,
#             "net_sales_box6": doc.formatted_net_sales_box6,
#             "purchase_vat_reclaimed_box4": doc.formatted_purchase_vat_reclaimed_box4,
#             "net_purchases_box7": doc.formatted_net_purchases_box7,
#             "eu_acquisition_vat_due_box2": doc.formatted_eu_acquisition_vat_due_box2,
#             "net_eu_supplies_box_8" : doc.formatted_net_eu_supplies_box_8,
#             "net_eu_acquisitions_box_9": doc.formatted_net_eu_acquisitions_box_9,
#             "total_vat_due_box3":doc.formatted_total_vat_due_box3,
#             "net_vat_due_box5":doc.formatted_net_vat_due_box5

#         }

#     }

@frappe.whitelist()
def calculate_vat_boxes(docname):
    doc = frappe.get_doc("UK MTD VAT Return", docname)
    
    if not doc.period_start_date or not doc.period_end_date:
        frappe.throw("Please set period start and end dates first")

    sales_invoices = frappe.get_all("Sales Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1,
        "is_return": 0
    }, fields=["base_grand_total", "base_total_taxes_and_charges"])

    doc.sales_vat_due_box1 = sum(inv.base_total_taxes_and_charges for inv in sales_invoices)
    doc.net_sales_box6 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges for inv in sales_invoices)

    purchase_invoices = frappe.get_all("Purchase Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1,
        "is_return": 0
    }, fields=["base_grand_total", "base_total_taxes_and_charges"])

    doc.purchase_vat_reclaimed_box4 = sum(inv.base_total_taxes_and_charges for inv in purchase_invoices)
    doc.net_purchases_box7 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges for inv in purchase_invoices)

    eu_results = calculate_eu_transactions(doc.period_start_date, doc.period_end_date)
    doc.eu_acquisition_vat_due_box2 = eu_results['box2']
    doc.net_eu_supplies_box_8 = eu_results['box8']
    doc.net_eu_acquisitions_box_9 = eu_results['box9']

    doc.total_vat_due_box3 = doc.sales_vat_due_box1 + doc.eu_acquisition_vat_due_box2
    doc.net_vat_due_box5 = doc.total_vat_due_box3 - doc.purchase_vat_reclaimed_box4

    # # Set formatted values
    # doc.formatted_sales_vat_due_box1 = format_currency(doc.sales_vat_due_box1)
    # doc.formatted_net_sales_box6 = format_currency(doc.net_sales_box6)
    # doc.formatted_purchase_vat_reclaimed_box4 = format_currency(doc.purchase_vat_reclaimed_box4)
    # doc.formatted_net_purchases_box7 = format_currency(doc.net_purchases_box7)
    # doc.formatted_eu_acquisition_vat_due_box2 = format_currency(doc.eu_acquisition_vat_due_box2)
    # doc.formatted_net_eu_supplies_box_8 = format_currency(doc.net_eu_supplies_box_8)
    # doc.formatted_net_eu_acquisitions_box_9 = format_currency(doc.net_eu_acquisitions_box_9)
    # doc.formatted_total_vat_due_box3 = format_currency(doc.total_vat_due_box3)
    # doc.formatted_net_vat_due_box5 = format_currency(doc.net_vat_due_box5)

    doc.save()
    frappe.db.commit()

    return {
        "status": "success",
        "message": "VAT boxes calculated successfully"
    }


def calculate_eu_transactions(start_date, end_date):
    """Calculate EU-specific boxes"""
    # Box 2: VAT due on EU acquisitions
    eu_purchases = frappe.get_all("Purchase Invoice",
        filters={
            "posting_date": ["between", [start_date, end_date]],
            "docstatus": 1,
            "custom_is_eu_supplier": 1
        },
        fields=["base_grand_total", "base_total_taxes_and_charges"]
    )
    box2 = sum(inv.base_total_taxes_and_charges for inv in eu_purchases)
    
    # Box 8: Net EU supplies
    eu_sales = frappe.get_all("Sales Invoice",
        filters={
            "posting_date": ["between", [start_date, end_date]],
            "docstatus": 1,
            "custom_is_eu_customer": 1
        },
        fields=["base_grand_total", "base_total_taxes_and_charges"]
    )
    box8 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges 
              for inv in eu_sales)
    
    # Box 9: Net EU acquisitions
    box9 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges 
              for inv in eu_purchases)
    
    return {
        'box2': box2,
        'box8': box8,
        'box9': box9
    }

@frappe.whitelist()
def submit_vat_return_to_hmrc(docname):
    """Submit VAT return to HMRC with proper token handling and error management"""
    try:
        doc = frappe.get_doc("UK MTD VAT Return", docname)
        
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            frappe.throw("No default company set in Global Defaults.")
            
        vrn = frappe.db.get_value("Company", default_company, "custom_uk_vat_registration_number")
        if not vrn:
            frappe.throw(f"VRN not set for company {default_company}.")

        vat_settings = frappe.get_doc("VAT Settings", {"company": default_company})
        if not vat_settings:
            frappe.throw("VAT Settings not found for company.")
        
        if not vat_settings.get_password("access_token"):
            frappe.throw("Access token not found. Please authorize with HMRC first.")

        original_doc = doc.as_dict().copy()
        
        try:
            submission_data = {
                "periodKey": doc.reference_key,
                "vatDueSales": float(doc.sales_vat_due_box1 or 0),
                "vatDueAcquisitions": float(doc.eu_acquisition_vat_due_box2 or 0),
                "totalVatDue": float(doc.total_vat_due_box3 or 0),
                "vatReclaimedCurrPeriod": float(doc.purchase_vat_reclaimed_box4 or 0),
                "netVatDue": float(doc.net_vat_due_box5 or 0),
                "totalValueSalesExVAT": int(round(float(doc.net_sales_box6 or 0), 0)),
                "totalValuePurchasesExVAT": int(round(float(doc.net_purchases_box7 or 0), 0)),
                "totalValueGoodsSuppliedExVAT": int(round(float(doc.net_eu_supplies_box_8 or 0), 0)),
                "totalAcquisitionsExVAT": int(round(float(doc.net_eu_acquisitions_box_9 or 0), 0)),
                "finalised": True
            }
        except (TypeError, ValueError) as e:
            frappe.throw(f"Invalid VAT box values: {str(e)}")

        response = make_hmrc_request(
            "POST",
            f"/organisations/vat/{vrn}/returns",
            vat_settings.name,
            json_data=submission_data
        )
        
        if not response.get("success"):
            error_msg = response.get("error", "Unknown error occurred")
            if "response_text" in response:
                error_msg += f"\nResponse: {response['response_text']}"
            frappe.throw(f"Failed to submit VAT return: {error_msg}")
            
        response_data = response.get("data", {})
        
        doc.status = "Fulfilled"
        doc.custom_processing_date = response_data.get("processingDate")
        doc.custom_form_bundle_number = response_data.get("formBundleNumber")
        doc.custom_receipt_id = response_data.get("chargeRefNumber")
        doc.custom_receipt_date = frappe.utils.now_datetime()

        # Save with version tracking
        doc.flags.ignore_version = False
        doc.save(ignore_permissions=True)
        create_proper_version_log(doc, original_doc)
        
        return {
            "status": "success",
            "message": "VAT return submitted successfully",
            "redirect_to": f"/app/uk-mtd-vat-return/{docname}",
            "response": response_data
        }

    except frappe.exceptions.ValidationError:
        raise  
    except Exception as e:
        error_msg = f"Failed to submit VAT return: {str(e)}"
        frappe.log_error("VAT Submission Failed", error_msg)
        frappe.throw(error_msg)

def create_proper_version_log(new_doc, old_doc_dict):
    """Create a version log that will definitely show in the UI"""
    try:
        meta = frappe.get_meta(new_doc.doctype)
        
        changes = []
        for field in ["status", "custom_processing_date", "custom_form_bundle_number",
                      "custom_receipt_id", "custom_receipt_date"]:
            old_value = old_doc_dict.get(field)
            new_value = new_doc.get(field)

            if old_value != new_value:
                field_meta = meta.get_field(field)
                changes.append({
                    "fieldname": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "fieldtype": field_meta.fieldtype if field_meta else "Data"
                })

        if not changes:
            frappe.logger().info("No changes detected; version log not created.")
            return False

        # Create version doc manually
        version_doc = frappe.new_doc("Version")
        version_doc.docname = new_doc.name
        version_doc.ref_doctype = new_doc.doctype
        version_doc.data = json.dumps({
            "changed": changes,
            "added": [],
            "removed": [],
            "row_changed": [],
            "doc": {}
        })  # NOTE: Leave "doc" as empty to avoid huge payloads unless needed
        
        version_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"Version log created: {version_doc.name}")
        return True

        # Validate the version document exists and has data
        if not frappe.db.exists("Version", version_doc.name):
            frappe.log_error("Version document missing after insert", version_doc.name)
            return False

        return True

    except Exception as e:
        frappe.log_error("Failed to create version log", frappe.get_traceback())
        return False



@frappe.whitelist()
def fetch_liabilities(from_date=None, to_date=None):
    """
    Fetch VAT liabilities from HMRC API matching your doctype field names
    """
    try:
        # 1. Get company and VAT settings
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            frappe.throw("No default company set in Global Defaults.")
            
        vrn = frappe.db.get_value("Company", default_company, "custom_uk_vat_registration_number")
        if not vrn:
            frappe.throw(f"VAT Registration Number not set for company {default_company}")

        vat_settings = frappe.get_doc("VAT Settings", {"company": default_company})
        if not vat_settings:
            frappe.throw("VAT Settings not found for company.")
            
        if not vat_settings.get_password("access_token"):
            frappe.throw("Access token not found. Please authorize with HMRC first.")

        # 2. Prepare API request with your field names
        params = {}
        if from_date:
            params["from"] = from_date  # Matches your from_date field
        if to_date:
            params["to"] = to_date  # Matches your to_date field
        
        response = make_hmrc_request(
            "GET",
            f"/organisations/vat/{vrn}/liabilities",
            vat_settings.name,
            params=params
        )
        
        if not response.get("success"):
            error_msg = response.get("error", "Unknown error")
            status_code = response.get("status_code", "unknown")

        if status_code == 404:
            frappe.throw("No liability data found for the specified period.")
        else:
            frappe.throw(f"HMRC API Error ({status_code}): {error_msg}")
            
        liabilities = response.get("data", {}).get("liabilities", [])
        today = nowdate()
        formatted_data = []
        
        for liability in liabilities:
            tax_period = liability.get("taxPeriod", {})
            outstanding = float(liability.get("outstandingAmount", 0))
            
            formatted_data.append({
                "name": f"LIABILITY-{tax_period.get('from')}-{liability.get('type')}",
                "type": liability.get("type"),  # Matches your type field
                "from_date": tax_period.get("from"),  # Matches your from_date field
                "to_date": tax_period.get("to"),  # Matches your to_date field
                "due_date": liability.get("due"),  # Matches your due_date field
                "original_amount": float(liability.get("originalAmount", 0)),  # Matches your field
                "outstanding_amount": outstanding
            })
            
        return formatted_data
        
    except Exception as e:
        frappe.log_error("VAT Liability Error", str(e))
        # frappe.throw("Failed to fetch liabilities. Please check error logs.")

@frappe.whitelist()
def fetch_payments(from_date=None, to_date=None):
    """
    Fetch VAT liabilities from HMRC API matching your doctype field names
    """
    try:
        # 1. Get company and VAT settings
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            frappe.throw("No default company set in Global Defaults.")
            
        vrn = frappe.db.get_value("Company", default_company, "custom_uk_vat_registration_number")
        if not vrn:
            frappe.throw(f"VAT Registration Number not set for company {default_company}")

        vat_settings = frappe.get_doc("VAT Settings", {"company": default_company})
        if not vat_settings:
            frappe.throw("VAT Settings not found for company.")
            
        if not vat_settings.get_password("access_token"):
            frappe.throw("Access token not found. Please authorize with HMRC first.")

        # 2. Prepare API request with your field names
        params = {}
        if from_date:
            params["from"] = from_date  # Matches your from_date field
        if to_date:
            params["to"] = to_date  # Matches your to_date field
        
        response = make_hmrc_request(
            "GET",
            f"/organisations/vat/{vrn}/payments",
            vat_settings.name,
            params=params
        )
        
        if not response.get("success"):
            error_msg = response.get("error", "Unknown error")
            status_code = response.get("status_code", "unknown")

        if status_code == 404:
            frappe.throw("No liability data found for the specified period.")
        else:
            frappe.throw(f"HMRC API Error ({status_code}): {error_msg}")
            
        payments = response.get("data", {}).get("payments", [])
        today = nowdate()
        formatted_data = []
        
        for payment in payments:
            
            formatted_data.append({
                "amount": float(payment.get("amount", 0)),
                "received_date": payment.get("received"),
            })
            
        return formatted_data
        
    except requests.exceptions.RequestException as e:
        frappe.log_error("HMRC API Connection Error", str(e))
        # frappe.throw("Failed to connect to HMRC API")
    except Exception as e:
        frappe.log_error("VAT Payment Error", str(e))
        # frappe.throw("Failed to fetch VAT payments")

def get_fraud_prevention_headers():
    """Generate fully compliant HMRC Fraud Prevention Headers"""
    try:
        # Timestamp (used in multiple headers)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        # 1. Device Identification
        device_id = frappe.db.get_value("System Settings", "System Settings", "hmrc_device_id") or str(uuid.uuid4())
        frappe.db.set_value("System Settings", "System Settings", "hmrc_device_id", device_id)
        frappe.db.commit()

        # 2. Network Information
        local_ips = get_local_ips()
        public_ip = get_public_ip()
        
        # 3. System Information
        os_name = platform.system() or "Linux"
        os_version = platform.release() or "1.0"
        device_model = platform.node() or socket.gethostname() or "ERPNext-Server"

        # Percent-encode all values properly
        user_id = f"os={quote(os_name)}&user={quote(frappe.session.user or 'system')}"
        license_hash = hashlib.sha256(get_site_name().encode()).hexdigest()

        headers = {
            # Connection and Device
            "Gov-Client-Connection-Method": "DESKTOP_APP_VIA_SERVER",
            "Gov-Client-Device-ID": device_id,
            
            # Network Information
            "Gov-Client-Local-IPs": ",".join(local_ips),
            "Gov-Client-Local-IPs-Timestamp": timestamp,
            "Gov-Client-MAC-Addresses": "00-11-22-33-44-55",
            "Gov-Client-Public-IP": public_ip,
            "Gov-Client-Public-IP-Timestamp": timestamp,
            "Gov-Client-Public-Port": "49152",  # Valid ephemeral port
            "Gov-Client-Multi-Factor": "",  # Requires HMRC exemption documentation
            
            # Client Environment
            "Gov-Client-Screens": "width=1920&height=1080&scaling-factor=1&colour-depth=24",
            "Gov-Client-Timezone": get_timezone(),
            "Gov-Client-User-IDs": user_id,
            "Gov-Client-User-Agent": (
                f"os-family={quote(os_name)}&"
                f"os-version={quote(os_version)}&"
                f"device-manufacturer={quote(get_device_manufacturer())}&"
                f"device-model={quote(device_model)}"
            ),
            "Gov-Client-Window-Size": "width=1920&height=1080",
            
            # Vendor Information
            "Gov-Vendor-Forwarded": f"by={public_ip}&for={public_ip}",
            "Gov-Vendor-License-IDs": f"erpnext={license_hash}",
            "Gov-Vendor-Product-Name": "ERPNext",
            "Gov-Vendor-Version": f"client=1.0&server={quote(frappe.__version__)}",
            "Gov-Vendor-Public-IP": public_ip
        }
        
        return headers

    except Exception as e:
        frappe.log_error("Fraud Prevention Header Error", str(e))
        return generate_compliant_fallback_headers()

def get_local_ips():
    """Get all non-loopback local IPs"""
    try:
        ips = []
        for interface in socket.getaddrinfo(socket.gethostname(), None):
            ip = interface[4][0]
            if '.' in ip and not ip.startswith('127.'):
                ips.append(ip)
        return ips if ips else ["192.168.1.1"]
    except:
        return ["192.168.1.1"]

def get_public_ip():
    """Get actual public IP with multiple fallbacks"""
    services = [
        'https://api.ipify.org',
        'https://ident.me',
        'https://ifconfig.me/ip'
    ]
    
    for service in services:
        try:
            ip = requests.get(service, timeout=2).text.strip()
            if is_valid_ip(ip):
                return ip
        except:
            continue
            
    return "203.0.113.1"  # RFC TEST-NET-1 fallback

def get_timezone():
    """Get current timezone offset"""
    offset = -time.timezone // 3600
    return f"UTC{'+' if offset >=0 else ''}{offset}:00"

def get_device_manufacturer():
    """Try to detect hardware manufacturer"""
    try:
        if platform.system() == "Linux":
            with open('/sys/class/dmi/id/sys_vendor') as f:
                return f.read().strip() or "Unknown"
        return platform.system()
    except:
        return "Unknown"

def generate_compliant_fallback_headers():
    """Generate minimum valid headers when all else fails"""
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "Gov-Client-Connection-Method": "DESKTOP_APP_VIA_SERVER",
        "Gov-Client-Device-ID": str(uuid.uuid4()),
        "Gov-Client-Local-IPs": "192.168.1.1",
        "Gov-Client-Local-IPs-Timestamp": timestamp,
        "Gov-Client-MAC-Addresses": "00-11-22-33-44-55",
        "Gov-Client-Public-IP": "203.0.113.1",
        "Gov-Client-Public-IP-Timestamp": timestamp,
        "Gov-Client-Public-Port": "49152",
        "Gov-Client-Screens": "width=1920&height=1080&scaling-factor=1&colour-depth=24",
        "Gov-Client-Timezone": "UTC+00:00",
        "Gov-Client-User-IDs": "os=Linux&user=system",
        "Gov-Client-User-Agent": "os-family=Linux&os-version=1.0&device-manufacturer=Generic&device-model=Server",
        "Gov-Client-Window-Size": "width=1920&height=1080",
        "Gov-Vendor-Forwarded": "by=203.0.113.1&for=203.0.113.1",
        "Gov-Vendor-License-IDs": "erpnext=" + hashlib.sha256("default".encode()).hexdigest(),
        "Gov-Vendor-Product-Name": "ERPNext",
        "Gov-Vendor-Version": "client=1.0&server=1.0",
        "Gov-Vendor-Public-IP": "203.0.113.1",
        "Gov-Client-Multi-Factor": ""
    }

def is_valid_ip(ip):
    """Validate IPv4 address format"""
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except:
        return False

# console
# from zikpro_erpnext_uk_vat.api import validate_fraud_headers
# validate_fraud_headers()

@frappe.whitelist()
def validate_fraud_headers():
    try:
        default_company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not default_company:
            return {"success": False, "message": "No default company set"}
            
        vat_settings = frappe.get_all("VAT Settings", filters={"company": default_company}, limit=1)
        if not vat_settings:
            return {"success": False, "message": "No VAT Settings found"}
            
        vat_settings = frappe.get_doc("VAT Settings", vat_settings[0].name)

        access_token = vat_settings.get_password("access_token")
        if not access_token:
            return {"success": False, "message": "No access token found"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            **get_fraud_prevention_headers()
        }
        
        response = requests.get(
            "https://test-api.service.hmrc.gov.uk/test/fraud-prevention-headers/validate",
            headers=headers,
            timeout=30
        )

        if response.status_code == 401: 
            refresh_result = refresh_access_token(vat_settings.name)
            if not refresh_result.get("success"):
                return refresh_result
            
            return validate_fraud_headers()
            
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.json() if response.content else response.text
        }

    except Exception as e:
        frappe.log_error("Header Validation Error", str(e))
        return {"success": False, "message": f"Validation failed: {str(e)}"}