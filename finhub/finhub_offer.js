frappe.ui.form.on('Finhub Offer', {
    setup: function(frm) {
        // Set query for products - only show active ones
        frm.set_query('product', function() {
            return {
                filters: {
                    'is_active': 1
                }
            };
        });
    },
    
    customer: function(frm) {
        if (frm.doc.customer) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Customer',
                    filters: { name: frm.doc.customer },
                    fieldname: ['territory', 'customer_group', 'default_currency']
                },
                callback: function(r) {
                    if (r.message) {
                        if (!frm.doc.territory) {
                            frm.set_value('territory', r.message.territory);
                        }
                        if (!frm.doc.customer_group) {
                            frm.set_value('customer_group', r.message.customer_group);
                        }
                        if (!frm.doc.currency) {
                            frm.set_value('currency', r.message.default_currency || 'INR');
                        }
                        frm.refresh_fields();
                    }
                }
            });
        }
    },
    
    product: function(frm) {
        if (frm.doc.product) {
            // Clear existing items
            frm.clear_table('items');
            frm.refresh_field('items');
            
            // Show loading
            frappe.show_alert({
                message: __('Loading product features...'),
                indicator: 'orange'
            }, 3);
            
            // Call server method to get features
            frm.call({
                method: 'get_product_features',
                doc: frm.doc,
                callback: function(r) {
                    frm.refresh_field('items');
                    frm.trigger('calculate_total');
                    
                    if (r.message && r.message.length > 0) {
                        frappe.show_alert({
                            message: __(r.message.length + ' features loaded'),
                            indicator: 'green'
                        }, 3);
                    }
                },
                error: function(err) {
                    console.error(err);
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to load features. Check console for details.'),
                        indicator: 'red'
                    });
                }
            });
        } else {
            frm.clear_table('items');
            frm.set_value('total_amount', 0);
            frm.refresh_field('items');
            frm.refresh_field('total_amount');
        }
    },
    
    calculate_total: function(frm) {
        let total = 0;
        let items = frm.doc.items || [];
        
        items.forEach(item => {
            let qty = flt(item.qty);
            let rate = flt(item.rate);
            let amount = qty * rate;
            
            // Update the amount in the child table
            frappe.model.set_value(item.doctype, item.name, 'amount', amount);
            total += amount;
        });
        
        frm.set_value('total_amount', total);
        frm.refresh_field('total_amount');
    },
    
    refresh: function(frm) {
        // Add custom button for testing
        if (frm.doc.__islocal) {
            frm.add_custom_button(__('Load Features'), function() {
                if (frm.doc.product) {
                    frm.trigger('product');
                } else {
                    frappe.msgprint('Please select a product first');
                }
            });
        }
    }
});

// Child table triggers
frappe.ui.form.on('Offer Item', {
    qty: function(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        
        // If base_rate exists, recalculate rate with discount
        if (row.base_rate && row.discount_percentage) {
            let new_rate = row.base_rate * (1 - (row.discount_percentage / 100));
            frappe.model.set_value(cdt, cdn, 'rate', new_rate);
        }
        
        frm.trigger('calculate_total');
    },
    
    rate: function(frm) {
        frm.trigger('calculate_total');
    },
    
    items_remove: function(frm) {
        frm.trigger('calculate_total');
    }
});
