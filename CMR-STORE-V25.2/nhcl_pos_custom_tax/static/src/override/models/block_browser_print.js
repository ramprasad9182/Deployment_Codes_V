/** @odoo-module **/

// Wrap window.print to track when Odoo POS initiates printing programmatically
const originalPrint = window.print;
window.print = function () {
    window.pos_printing_active = true;
    originalPrint.apply(this, arguments);
};

// Listen to beforeprint event to hide POS content if printed from the browser settings menu
window.addEventListener('beforeprint', () => {
    if (!window.pos_printing_active) {
        document.body.classList.add('pos-hide-on-print');
    }
});

// Clean up classes and flags after the print dialog is closed
window.addEventListener('afterprint', () => {
    document.body.classList.remove('pos-hide-on-print');
    window.pos_printing_active = false;
});
