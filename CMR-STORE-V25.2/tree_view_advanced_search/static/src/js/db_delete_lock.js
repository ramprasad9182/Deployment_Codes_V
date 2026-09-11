/** @odoo-module **/

function initDeleteLock() {
    const dropForm = document.getElementById("form_drop_db");

    if (!dropForm) {
        setTimeout(initDeleteLock, 500);
        return;
    }

    const deleteBtn = dropForm.querySelector(
        'input[type="submit"][value="Delete"]'
    );

    if (!deleteBtn) {
        return;
    }

    // Disable Delete button by default
    deleteBtn.setAttribute("disabled", "disabled");
}

initDeleteLock();