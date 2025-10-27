import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    if not filters.get("vat_return"):
        frappe.throw("Please select a VAT Return")

    doc = frappe.get_doc("UK MTD VAT Return", filters.get("vat_return"))
    if not doc.period_start_date or not doc.period_end_date:
        frappe.throw("Please set Period Start and End Dates in the VAT Return")

    # Fetch invoices
    sales_invoices = frappe.get_all("Sales Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1
    }, fields=["name", "customer_name", "posting_date", "base_grand_total", "base_total_taxes_and_charges"])

    purchase_invoices = frappe.get_all("Purchase Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1
    }, fields=["name", "supplier_name", "posting_date", "base_grand_total", "base_total_taxes_and_charges"])

    boxes = calculate_vat_boxes_data(doc)

    columns = [
        {"label": "Type", "fieldname": "invoice_type", "fieldtype": "Data", "width": 100},
        {"label": "Invoice", "fieldname": "invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": "Party", "fieldname": "party", "fieldtype": "Data", "width": 150},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
        {"label": "Taxes", "fieldname": "taxes", "fieldtype": "Currency", "width": 130},
    ]

    data = []
    for inv in sales_invoices:
        data.append({
            "invoice_type": "Sales Invoice",
            "invoice": inv.name,
            "party": inv.customer_name,
            "posting_date": inv.posting_date,
            "grand_total": inv.base_grand_total,
            "taxes": inv.base_total_taxes_and_charges
        })

    for inv in purchase_invoices:
        data.append({
            "invoice_type": "Purchase Invoice",
            "invoice": inv.name,
            "party": inv.supplier_name,
            "posting_date": inv.posting_date,
            "grand_total": inv.base_grand_total,
            "taxes": inv.base_total_taxes_and_charges
        })

    return columns, data, None, None, get_summary(boxes)


def calculate_vat_boxes_data(doc):
    """Recalculate VAT boxes without saving to doc"""
    sales_invoices = frappe.get_all("Sales Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1,
        "is_return": 0
    }, fields=["base_grand_total", "base_total_taxes_and_charges"])

    purchase_invoices = frappe.get_all("Purchase Invoice", filters={
        "posting_date": ["between", [doc.period_start_date, doc.period_end_date]],
        "docstatus": 1,
        "is_return": 0
    }, fields=["base_grand_total", "base_total_taxes_and_charges"])

    # Temporarily skip EU data if function not available
    eu_results = {"box2": 0, "box8": 0, "box9": 0}

    box1 = sum(inv.base_total_taxes_and_charges for inv in sales_invoices)
    box6 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges for inv in sales_invoices)
    box4 = sum(inv.base_total_taxes_and_charges for inv in purchase_invoices)
    box7 = sum(inv.base_grand_total - inv.base_total_taxes_and_charges for inv in purchase_invoices)
    box2 = eu_results['box2']
    box8 = eu_results['box8']
    box9 = eu_results['box9']
    box3 = box1 + box2
    box5 = box3 - box4

    return {
        "Box 1 - VAT Due on Sales": box1,
        "Box 2 - VAT Due on EU Acquisitions": box2,
        "Box 3 - Total VAT Due": box3,
        "Box 4 - VAT Reclaimed Current Period": box4,
        "Box 5 - Net VAT Due": box5,
        "Box 6 - Total Sales Ex VAT": box6,
        "Box 7 - Total Purchases Ex VAT": box7,
        "Box 8 - Value of Goods Supplied to EU": box8,
        "Box 9 - Value of Goods Acquired from EU": box9
    }


def get_summary(boxes):
    """Return VAT boxes as styled summary cards"""
    return [
        {"label": "Box 1 - VAT Due on Sales", "value": boxes["Box 1 - VAT Due on Sales"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 2 - VAT Due on EU Acquisitions", "value": boxes["Box 2 - VAT Due on EU Acquisitions"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 3 - Total VAT Due", "value": boxes["Box 3 - Total VAT Due"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 4 - VAT Reclaimed Current Period", "value": boxes["Box 4 - VAT Reclaimed Current Period"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 5 - Net VAT Due", "value": boxes["Box 5 - Net VAT Due"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 6 - Total Sales Ex VAT", "value": boxes["Box 6 - Total Sales Ex VAT"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 7 - Total Purchases Ex VAT", "value": boxes["Box 7 - Total Purchases Ex VAT"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 8 - Value of Goods Supplied to EU", "value": boxes["Box 8 - Value of Goods Supplied to EU"], "indicator": "black", "datatype": "Currency"},
        {"label": "Box 9 - Value of Goods Acquired from EU", "value": boxes["Box 9 - Value of Goods Acquired from EU"], "indicator": "black", "datatype": "Currency"}
    ]
