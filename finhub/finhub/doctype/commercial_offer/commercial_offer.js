frappe.ui.form.on('Commercial Offer', {

    refresh: function(frm) {

        if (
            frm.doc.docstatus === 1 &&
            (
                frm.doc.status === 'Approval' ||
                frm.doc.status === 'Sent'
            )
        ) {

            frm.add_custom_button(
                __('Send to DocuSign'),
                () => {

                    frm.call('send_to_docusign')
                        .then(response => {

                            if (
                                response &&
                                response.message &&
                                response.message.status === 'success'
                            ) {

                                frappe.show_alert({
                                    message: __('Envelope sent successfully'),
                                    indicator: 'green'
                                });

                                frm.reload_doc();

                            } else {

                                frappe.msgprint({
                                    title: __('DocuSign Error'),
                                    indicator: 'red',
                                    message:
                                        response.message.message ||
                                        __('Unknown Error')
                                });
                            }
                        });

                }
            ).addClass('btn-primary');
        }

        if (frm.doc.docusign_envelope_id) {

            frm.add_custom_button(
                __('View DocuSign Envelope'),
                () => {

                    window.open(
                        `https://demo.docusign.net/Member/EnvelopeDetails.aspx?envelopeId=${frm.doc.docusign_envelope_id}`,
                        '_blank'
                    );

                },
                __('Links')
            );
        }

        if (frm.doc.custom_ticket_id) {

            frm.add_custom_button(
                __('View Fulfillment Ticket'),
                () => {

                    frappe.set_route(
                        'Form',
                        'Issue',
                        frm.doc.custom_ticket_id
                    );

                },
                __('Links')
            );
        }
    },

    vertical: function(frm) {

        trigger_server_recalc(frm);
    },

    country: function(frm) {

        trigger_server_recalc(frm);
    }
});


frappe.ui.form.on('Offer Line Item', {

    finhub_module: function(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        if (!row.finhub_module) {
            return;
        }

        frm.call({
            doc: frm.doc,
            method: 'get_module_data',
            args: {
                finhub_module: row.finhub_module
            },
            callback: function(r) {

                if (
                    r.message &&
                    r.message.base_price !== undefined
                ) {

                    // STORE MASTER INR VALUE
                    frappe.model.set_value(
                        cdt,
                        cdn,
                        'base_rate_inr',
                        r.message.base_price
                    );

                    // TEMP DISPLAY VALUE
                    frappe.model.set_value(
                        cdt,
                        cdn,
                        'base_rate',
                        r.message.base_price
                    );

                    frappe.model.set_value(
                        cdt,
                        cdn,
                        'rate',
                        r.message.base_price
                    );

                    calculate_row_amount(
                        frm,
                        cdt,
                        cdn
                    );

                    // RECALCULATE AFTER VALUES SAVED
                    setTimeout(() => {

                        trigger_server_recalc(frm);

                    }, 200);
                }
            }
        });
    },

    qty: function(frm, cdt, cdn) {

        calculate_row_amount(
            frm,
            cdt,
            cdn
        );

        trigger_server_recalc(frm);
    },

    rate: function(frm, cdt, cdn) {

        calculate_row_amount(
            frm,
            cdt,
            cdn
        );

        trigger_server_recalc(frm);
    },

    items_remove: function(frm) {

        trigger_server_recalc(frm);
    }
});


function calculate_row_amount(frm, cdt, cdn) {

    let row = locals[cdt][cdn];

    let qty = flt(row.qty);

    let rate = flt(row.rate);

    let amount = qty * rate;

    frappe.model.set_value(
        cdt,
        cdn,
        'amount',
        amount
    );
}


function trigger_server_recalc(frm) {

    if (
        !frm.doc.items ||
        frm.doc.items.length === 0
    ) {

        frm.set_value(
            'total_amount',
            0
        );

        return;
    }

    frm.call({
        doc: frm.doc,
        method: 'calculate_client_side_totals',
        callback: function(r) {

            if (!r.message) {
                return;
            }

            // TOTAL
            frm.set_value(
                'total_amount',
                flt(r.message.total_amount)
            );

            // CURRENCY
            if (r.message.currency) {

                frm.set_value(
                    'currency',
                    r.message.currency
                );
            }

            // COMPANY
            if (r.message.company) {

                frm.set_value(
                    'company',
                    r.message.company
                );
            }

            // BRANCH
            if (r.message.branch) {

                frm.set_value(
                    'branch',
                    r.message.branch
                );
            }

            // SALES MANAGER
            if (r.message.sales_manager_email) {

                frm.set_value(
                    'sales_manager_email',
                    r.message.sales_manager_email
                );
            }

            // CONVERSION RATE
            if (r.message.conversion_rate) {

                frm.set_value(
                    'conversion_rate',
                    r.message.conversion_rate
                );
            }

            // UPDATE ITEMS
            if (r.message.items) {

                r.message.items.forEach(updated_row => {

                    let row = locals[
                        updated_row.doctype
                    ][
                        updated_row.name
                    ];

                    if (row) {

                        row.base_rate =
                            updated_row.base_rate;

                        row.rate =
                            updated_row.rate;

                        row.amount =
                            updated_row.amount;
                    }
                });

                frm.refresh_field('items');
            }

            frm.refresh_field('total_amount');

            frm.refresh_field('currency');

            frm.refresh_field('company');

            frm.refresh_field('branch');

            frm.refresh_field('sales_manager_email');

            frm.refresh_field('conversion_rate');
        }
    });
}