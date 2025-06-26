frappe.listview_settings['UK MTD VAT Liability'] = {
    onload: function(listview) {
        // Create a wrapper div to hold the filters (recommended)
        const filter_wrapper = $(`<div class="flex gap-3 mb-3"></div>`).appendTo(listview.page.inner_toolbar || listview.page.wrapper);

        // FROM Date field
        const from_date = new frappe.ui.form.ControlDate({
            df: {
                label: __("From Date"),
                fieldname: "from_date",
                fieldtype: "Date",
                default: frappe.datetime.add_months(frappe.datetime.get_today(), -12)
            },
            parent: filter_wrapper.get(0),
        });
        from_date.make();

        // TO Date field
        const to_date = new frappe.ui.form.ControlDate({
            df: {
                label: __("To Date"),
                fieldname: "to_date",
                fieldtype: "Date",
                default: frappe.datetime.get_today()
            },
            parent: filter_wrapper.get(0),
        });
        to_date.make();

        // Store references
        listview.page.custom_filter_controls = {
            from_date,
            to_date
        };

        // Add button to fetch
        listview.page.add_inner_button(__("Fetch Liabilities"), function () {
             open_liability_fetch_dialog(listview);
        }, __("Actions"));
    }
};

function open_liability_fetch_dialog(listview) {
    const dialog = new frappe.ui.Dialog({
        title: __('Select Date Range'),
        fields: [
            {
                label: 'From Date',
                fieldname: 'from_date',
                fieldtype: 'Date',
                default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
                reqd: 1
            },
            {
                label: 'To Date',
                fieldname: 'to_date',
                fieldtype: 'Date',
                default: frappe.datetime.get_today(),
                reqd: 1
            }
        ],
        primary_action_label: __('Fetch'),
        primary_action(values) {
            if (values.from_date && values.to_date && new Date(values.from_date) > new Date(values.to_date)) {
                frappe.msgprint(__('From Date cannot be after To Date'));
                return;
            }

            dialog.hide(); // Close dialog

            frappe.call({
                method: "zikpro_erpnext_uk_vat.api.fetch_liabilities",
                args: {
                    from_date: values.from_date,
                    to_date: values.to_date
                },
                freeze: true,
                freeze_message: __("Fetching VAT liabilities from HMRC..."),
                callback: function (r) {
                    if (!r.message) {
                        frappe.msgprint(__("No data returned from HMRC API"));
                        return;
                    }

                    listview.data = r.message.map(item => ({
                        name: item.name || frappe.utils.get_random(10),
                        type: item.type,
                        from_date: item.from_date,
                        to_date: item.to_date,
                        due_date: item.due_date,
                        original_amount: item.original_amount,
                        outstanding_amount: item.outstanding_amount
                    }));

                    listview.render();
                    frappe.show_alert({
                        message: __("Fetched {0} liabilities", [r.message.length]),
                        indicator: "green"
                    });
                }
            });
        }
    });

    dialog.show();
}



// function refresh_liabilities(listview) {
//     const { from_date, to_date } = listview.page.custom_filter_controls || {};

//     const from_date_val = from_date?.get_value();
//     const to_date_val = to_date?.get_value();

//     if (from_date_val && to_date_val && new Date(from_date_val) > new Date(to_date_val)) {
//         frappe.msgprint(__("From Date cannot be after To Date"));
//         return;
//     }

//     frappe.call({
//         method: "zikpro_erpnext_uk_vat.api.fetch_liabilities",
//         args: {
//             from_date: from_date_val,
//             to_date: to_date_val
//         },
//         freeze: true,
//         freeze_message: __("Fetching VAT liabilities from HMRC..."),
//         callback: function(r) {
//             if (!r.message) {
//                 frappe.msgprint(__("No data returned from HMRC API"));
//                 return;
//             }

//             listview.data = r.message.map(item => ({
//                 name: item.name || frappe.utils.get_random(10),
//                 type: item.type,
//                 from_date: item.from_date,
//                 to_date: item.to_date,
//                 due_date: item.due_date,
//                 original_amount: item.original_amount,
//                 outstanding_amount: item.outstanding_amount
//             }));

//             listview.render();
//             frappe.show_alert({
//                 message: __("Fetched {0} liabilities", [r.message.length]),
//                 indicator: "green"
//             });
//         },
//         error: function(r) {
//             let error_msg = __("Failed to fetch liabilities");
//             if (r.responseJSON?.exc) {
//                 try {
//                     error_msg = JSON.parse(r.responseJSON.exc[0]).message || error_msg;
//                 } catch (e) {
//                     error_msg = r.responseJSON.exc[0];
//                 }
//             }
//             frappe.msgprint({
//                 title: __("Error"),
//                 message: error_msg
//             });
//         }
//     });
// }



function format_currency(value) {
    if (value == null || isNaN(value)) return "";
    return frappe.format(value, {
        fieldtype: "Currency",
        options: frappe.defaults.get_default("currency")
    });
}