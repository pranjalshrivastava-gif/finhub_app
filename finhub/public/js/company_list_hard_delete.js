frappe.listview_settings["Company"] = {

    onload(listview) {

        listview.page.add_action_item(
            __("Hard Delete Selected Companies"),
            async function () {

                const selected = listview.get_checked_items();

                if (!selected.length) {

                    frappe.msgprint({
                        title: __("No Companies Selected"),
                        message: __("Please select at least one company."),
                        indicator: "orange"
                    });

                    return;
                }

                const company_names = selected.map(doc => doc.name);

                frappe.confirm(
                    __(
                        "This will permanently delete selected companies and ALL linked records.<br><br>This action cannot be undone.<br><br>Continue?"
                    ),

                    async function () {

                        frappe.dom.freeze(__("Deleting Companies..."));

                        try {

                            const r = await frappe.call({
                                method: "finhub.api.company_delete.bulk_hard_delete_companies",
                                args: {
                                    companies: company_names
                                }
                            });

                            frappe.dom.unfreeze();

                            if (r.message.success) {

                                frappe.show_alert({
                                    message: __("Companies deleted successfully"),
                                    indicator: "green"
                                });

                                listview.refresh();

                            } else {

                                frappe.msgprint({
                                    title: __("Delete Failed"),
                                    message: r.message.message,
                                    indicator: "red"
                                });
                            }

                        } catch (e) {

                            frappe.dom.unfreeze();

                            frappe.msgprint({
                                title: __("Server Error"),
                                message: e.message,
                                indicator: "red"
                            });
                        }
                    }
                );
            }
        );

    }
};