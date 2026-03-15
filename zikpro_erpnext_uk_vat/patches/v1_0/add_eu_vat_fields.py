import frappe

def execute():
    create_custom_fields()

def create_custom_fields():
    fields = [
        # Company → UK VAT Registration Number
        {
            "doctype": "Custom Field",
            "dt": "Company",
            "fieldname": "uk_vat_registration_number",
            "label": "UK VAT Registration Number",
            "fieldtype": "Data",
            "insert_after": "parent_company",
            "unique": 1,
        },

        # Purchase Invoice → Is EU Supplier
        {
            "doctype": "Custom Field",
            "dt": "Purchase Invoice",
            "fieldname": "is_eu_supplier",
            "label": "Is EU Supplier",
            "fieldtype": "Check",
            "insert_after": "supplier",
            "default": 0,
        },

        # Sales Invoice → Is EU Customer
        {
            "doctype": "Custom Field",
            "dt": "Sales Invoice",
            "fieldname": "is_eu_customer",
            "label": "Is EU Customer",
            "fieldtype": "Check",
            "insert_after": "customer",
            "default": 0,
        },
    ]

    for field in fields:
        field_name = f"{field['dt']}-{field['fieldname']}"
        if not frappe.db.exists("Custom Field", field_name):
            frappe.get_doc(field).insert(ignore_permissions=True)

    frappe.clear_cache()