// Copyright (c) 2025, Zikpro and contributors
// For license information, please see license.txt

frappe.ui.form.on("VAT Settings", {
	refresh: function(frm) {
        frm.add_custom_button(__('Authorize with HMRC'), function() {
            frappe.call({
                method: 'zikpro_erpnext_uk_vat.api.start_oauth_flow',
                args: {
                    docname: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        window.open(r.message, '_blank');
                    }
                }
            });
        });
	},
});
