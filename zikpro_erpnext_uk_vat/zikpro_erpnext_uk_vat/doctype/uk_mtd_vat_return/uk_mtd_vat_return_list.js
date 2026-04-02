frappe.listview_settings['UK MTD VAT Return'] = {
    get_indicator: function (doc) {
        if (doc.status === "Fulfilled") {
            return [__("Fulfilled"), "green", "status,=,Fulfilled"];
        } else if (doc.status === "Overdue") {
            return [__("Overdue"), "red", "status,=,Overdue"];
        } else {
            return [__(doc.status), "gray", "status,=," + doc.status];
        }
    },
    onload: function(listview) {
        listview.page.add_button(__("Fetch Obligations"), function() {
            let d = new frappe.ui.Dialog({
                title: __("Fetch VAT Obligations"),
                fields: [
                    {
                        label: "Frequency",
                        fieldname: "frequency",
                        fieldtype: "Select",
                        options: ["Monthly", "Quarterly"],
                        default: "Quarterly",
                        reqd: 1
                    },
                    {
                        label: "From Date",
                        fieldname: "from_date",
                        fieldtype: "Date",
                        default: frappe.datetime.add_months(frappe.datetime.nowdate(), -12),
                        reqd: 1
                    },
                    {
                        label: "To Date",
                        fieldname: "to_date",
                        fieldtype: "Date",
                        default: frappe.datetime.nowdate(),
                        reqd: 1
                    }
                ],
                primary_action_label: __("Fetch"),
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: 'zikpro_erpnext_uk_vat.api.fetch_all_obligations',
                        args: {
                            //docname: "VAT Settings",
                            frequency: values.frequency,
                            from_date: values.from_date,
                            to_date: values.to_date
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __("Processed {0} obligations", [r.message.count]),
                                    indicator: 'green'
                                });
                                listview.refresh();
                            }
                        },
                        freeze: true,
                        freeze_message: __("Fetching {0} obligations...", [values.frequency])
                    });
                }
            });
            d.show();
        }).addClass("btn-primary");
    }
};

//actual code starts
// frappe.ui.form.on('UK MTD VAT Return', {
//     refresh: function(frm) {
//         if (frm.doc.docstatus === 0) {
//             frm.add_custom_button(__('Calculate VAT Boxes'), function() {
//                 frappe.call({
//                     method: 'zikpro_erpnext_uk_vat.api.calculate_vat_boxes',
//                     args: { docname: frm.doc.name },
//                     callback: function(r) {
//                         if (!r.exc) {
//                             frappe.show_alert({
//                                 message: __('VAT boxes calculated successfully'),
//                                 indicator: 'green'
//                             });
//                             frm.refresh();
//                         }
//                     },
//                     freeze: true,
//                     freeze_message: __('Calculating VAT boxes...')
//                 });
//             }, __('VAT Return'));

//             if (frm.doc.status === "Overdue") {
//                 frm.add_custom_button(__('Submit to HMRC'), function() {
//                     frappe.confirm(
//                         __('<strong>UK HMRC Legal Declaration</strong><br><br>When you submit this VAT information you are making a legal declaration that the information is true and complete. A false declaration can result in prosecution.<br><br> Would you like to proceed?'),
//                         function() {  
//                             frappe.call({
//                                 method: 'zikpro_erpnext_uk_vat.api.submit_vat_return_to_hmrc',
//                                 args: { docname: frm.doc.name },
//                                 callback: function(r) {
//                                     if (!r.exc) {
//                                         frappe.show_alert({
//                                             message: __('VAT return submitted successfully! Redirecting...'),
//                                             indicator: 'green'
//                                         });
                                        
//                                         setTimeout(() => {
//                                             frappe.set_route("List", "UK MTD VAT Return");
//                                         }, 2000);
//                                     }
//                                 },
//                                 freeze: true,
//                                 freeze_message: __('Submitting to HMRC...')
//                             });
//                         },
//                         function() { 
//                             frappe.show_alert({
//                                 message: __('Submission cancelled'),
//                                 indicator: 'orange'
//                             });
//                         }
//                     );
//                 }, __('VAT Return')).addClass('btn-danger');
//             }
//         }
//         setup_box_calculations(frm); 
//     }
// });

//actual code ends

frappe.ui.form.on('UK MTD VAT Return', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // Calculate VAT Boxes button (unchanged)
            frm.add_custom_button(__('Calculate VAT Boxes'), function() {
                frappe.call({
                    method: 'zikpro_erpnext_uk_vat.api.calculate_vat_boxes',
                    args: { docname: frm.doc.name },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('VAT boxes calculated successfully'),
                                indicator: 'green'
                            });
                            frm.refresh();
                        }
                    },
                    freeze: true,
                    freeze_message: __('Calculating VAT boxes...')
                });
            }, __('VAT Return'));

            // Submit to HMRC button - now shows contact popup
            if (frm.doc.status === "Overdue") {
                frm.add_custom_button(__('Submit to HMRC'), function() {
                    // Show custom dialog instead of confirmation
                    const dialog = new frappe.ui.Dialog({
                        title: __('Contact Us for Submission'),
                        size: 'medium',
                        fields: [
                            {
                                fieldtype: 'HTML',
                                fieldname: 'contact_message',
                                options: `
                                    <div style="text-align: center; padding: 20px;">
                                        <i class="fa fa-envelope-o" style="font-size: 48px; color: #5e64ff; margin-bottom: 20px;"></i>
                                        <h4 style="margin-bottom: 15px;">${__('VAT Return Submission Service')}</h4>
                                        <p style="margin-bottom: 20px; color: #666;">
                                            ${__('To ensure accurate and compliant VAT submissions, please contact our team to assist with your HMRC submission.')}
                                        </p>
                                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                                            <p style="margin-bottom: 8px;">
                                                <i class="fa fa-phone" style="margin-right: 10px; color: #5e64ff;"></i>
                                                <strong>${__('Phone:')}</strong> <span style="color: #333;">+44 (0) 123 456 7890</span>
                                            </p>
                                            <p style="margin-bottom: 8px;">
                                                <i class="fa fa-envelope" style="margin-right: 10px; color: #5e64ff;"></i>
                                                <strong>${__('Email:')}</strong> <span style="color: #333;">vat.submissions@zikpro.com</span>
                                            </p>
                                            <p style="margin-bottom: 0;">
                                                <i class="fa fa-clock-o" style="margin-right: 10px; color: #5e64ff;"></i>
                                                <strong>${__('Hours:')}</strong> <span style="color: #333;">Mon-Fri, 9:00 - 17:00</span>
                                            </p>
                                        </div>
                                        <p style="color: #888; font-size: 12px;">
                                            <i class="fa fa-lock" style="margin-right: 5px;"></i>
                                            ${__('Our team will verify all calculations and ensure proper submission to HMRC')}
                                        </p>
                                    </div>
                                `
                            }
                        ],
                        primary_action_label: __('Close'),
                        primary_action: function() {
                            dialog.hide();
                        }
                    });
                    
                    // Add custom close button styling
                    dialog.set_primary_action(__('Close'), function() {
                        dialog.hide();
                    });
                    
                    dialog.show();
                    
                }, __('VAT Return')).addClass('btn-danger'); // Red button for emphasis
            }
        }
        setup_box_calculations(frm); // Your existing calculation setup
    }
});


function setup_box_calculations(frm) {
    frm.fields_dict['sales_vat_due_box1'].df.onchange = () => calculate_derived_boxes(frm);
    frm.fields_dict['eu_acquisition_vat_due_box2'].df.onchange = () => calculate_derived_boxes(frm);
    frm.fields_dict['purchase_vat_reclaimed_box4'].df.onchange = () => calculate_derived_boxes(frm);
}

function calculate_derived_boxes(frm) {
    // Box 3 = Box 1 + Box 2
    const box3 = (parseFloat(frm.doc.sales_vat_due_box1 || 0)) + 
                 (parseFloat(frm.doc.eu_acquisition_vat_due_box2 || 0));
    
    // Box 5 = Box 3 - Box 4
    const box5 = box3 - (parseFloat(frm.doc.purchase_vat_reclaimed_box4 || 0));
    
    frm.set_value('total_vat_due_box3', box3);
    frm.set_value('net_vat_due_box5', box5);
}
