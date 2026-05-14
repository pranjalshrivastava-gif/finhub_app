frappe.ui.form.on('Commercial Offer', {
    refresh: function(frm) {
        // Requirement 1.12 & 1.13: DocuSign Integration Button
        if (frm.doc.docstatus === 1 && frm.doc.status !== 'Signed') {
            frm.add_custom_button(__('Send to DocuSign'), () => {
                frappe.call({
                    method: 'finhub.finhub.api.automation.trigger_docusign',
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Connecting to DocuSign..."),
                    callback: function(r) {
                        if (r.message && r.message.status === "success") {
                            frappe.show_alert({
                                message: __('DocuSign Envelope Sent successfully'), 
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: __('Integration Error'),
                                indicator: 'red',
                                message: r.message ? r.message.reason : __("Unknown Error")
                            });
                        }
                    }
                });
            }).addClass('btn-primary');
        }

        // Requirement 1.11: Show link to Ticket if it exists
        if (frm.doc.custom_ticket_id) {
            frm.add_custom_button(__('View Fulfillment Ticket'), () => {
                frappe.set_route('Form', 'Issue', frm.doc.custom_ticket_id);
            }, __("Links"));
        }
    },

    vertical: function(frm) {
        // Requirement 1.6: Pricing Rules change based on Vertical
        if (frm.doc.vertical) {
            trigger_server_recalc(frm);
        }
    }
});

// Child Table Logic: Offer Line Item
frappe.ui.form.on('Offer Line Item', {
    finhub_module: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.finhub_module) {
            // Requirement 1.3: Fetch base price from Module DocType
            frm.call({
                doc: frm.doc,
                method: 'get_module_data',
                args: { finhub_module: row.finhub_module },
                callback: function(r) {
                    if (r.message && r.message.base_price) {
                        frappe.model.set_value(cdt, cdn, 'rate', r.message.base_price);
                        // trigger_server_recalc is called inside 'rate' trigger below
                    }
                }
            });
        }
    },

    qty: function(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },

    rate: function(frm, cdt, cdn) {
        calculate_row_amount(frm, cdt, cdn);
    },

    items_remove: function(frm) {
        trigger_server_recalc(frm);
    }
});

/**
 * Defensive calculation for row-level amounts
 */
function calculate_row_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let qty = flt(row.qty);
    let rate = flt(row.rate);
    let amount = qty * rate;
    
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    trigger_server_recalc(frm);
}

/**
 * Requirement 1.7: Pricing Computation Logic
 * Calls the Python controller to get the final total (with discounts) 
 * so the UI stays in sync with backend Pricing Rules.
 */
function trigger_server_recalc(frm) {
    // Prevent calling if items are empty to save resources
    if (!frm.doc.items || frm.doc.items.length === 0) {
        frm.set_value('total_amount', 0);
        return;
    }

    frm.call({
        doc: frm.doc,
        method: 'calculate_client_side_totals',
        callback: function(r) {
            if (r.message !== undefined) {
                // Use set_value to ensure the field is 'dirty' and ready for save
                frm.set_value('total_amount', flt(r.message));
                frm.refresh_field('total_amount');
            }
        }
    });
}