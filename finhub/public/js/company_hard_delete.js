frappe.ui.form.on("Company", {

    refresh(frm) {

        if (frm.is_new()) {
            return;
        }

        // Remove duplicate button
        frm.remove_custom_button(__("Hard Delete Company"));

        frm.add_custom_button(

            __("Hard Delete Company"),

            async function () {

                frappe.confirm(

                    `
                    <div style="line-height: 1.8;">

                        <h4 style="color: red;">
                            ${__("Permanent Deletion Warning")}
                        </h4>

                        <p>
                            ${__(
                                "This will permanently delete the Company and ALL linked records from the database."
                            )}
                        </p>

                        <ul>
                            <li>${__("Sales Invoices")}</li>
                            <li>${__("Purchase Invoices")}</li>
                            <li>${__("Journal Entries")}</li>
                            <li>${__("Payment Entries")}</li>
                            <li>${__("GL Entries")}</li>
                            <li>${__("Stock Entries")}</li>
                            <li>${__("Warehouses")}</li>
                            <li>${__("Accounts")}</li>
                            <li>${__("All linked transactional data")}</li>
                        </ul>

                        <br>

                        <b style="color: red;">
                            ${__("THIS ACTION CANNOT BE UNDONE")}
                        </b>

                    </div>
                    `,

                    async function () {

                        await execute_hard_delete(frm);

                    }

                );

            }

        ).addClass("btn-danger");

    }

});


async function execute_hard_delete(frm) {

    frappe.dom.freeze(
        __("Deleting Company And Linked Records...")
    );

    try {

        const r = await frappe.call({

            method: "finhub.api.company_delete.hard_delete_company",

            args: {
                company: frm.doc.name
            },

            freeze: false
        });

        frappe.dom.unfreeze();

        // ======================================================
        // SUCCESS
        // ======================================================

        if (r.message && r.message.success) {

            frappe.show_alert({

                message: __("Company Deleted Successfully"),

                indicator: "green"
            });

            setTimeout(() => {

                frappe.set_route("List", "Company");

            }, 1000);

            return;
        }

        // ======================================================
        // FAILED
        // ======================================================

        frappe.msgprint({

            title: __("Deletion Failed"),

            message: r.message.message || __("Unknown error"),

            indicator: "red"
        });

    } catch (e) {

        frappe.dom.unfreeze();

        console.error(e);

        frappe.msgprint({

            title: __("Server Error"),

            message: e.message || e,

            indicator: "red"
        });
    }
}