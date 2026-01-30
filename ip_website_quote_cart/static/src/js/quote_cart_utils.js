/** @odoo-module **/

const QUOTE_CART_QUANTITY_SESSION_NAME = 'quote_cart_quantity';

/**
 * Get the quote cart quantity from the session.
 *
 * @return {number} The quantity of items in the quote cart.
 */
function getQuoteCartQuantity() {
    return parseInt(sessionStorage.getItem(QUOTE_CART_QUANTITY_SESSION_NAME) || '0');
}

/**
 * Set the quote cart quantity in the session.
 *
 * @param {number} quantity The quantity of items in the quote cart.
 */
function setQuoteCartQuantity(quantity) {
    sessionStorage.setItem(QUOTE_CART_QUANTITY_SESSION_NAME, quantity.toString());
}

/**
 * Update the visibility and quantity of the quote cart button in the navbar.
 * Icon is hidden when cart is empty, shown when items are added.
 * Follows the same pattern as Odoo's updateCartNavBar for consistency.
 *
 * @param {number} quantity The quantity to display.
 */
function updateQuoteCartNavBar(quantity) {
    setQuoteCartQuantity(quantity);
    
    // Mobile and Desktop elements have to be updated (same pattern as Odoo)
    const cartQuantityElements = document.querySelectorAll('.my_qoute_cart_quantity');
    
    for (const cartQuantityElement of cartQuantityElements) {
        if (quantity === 0) {
            cartQuantityElement.classList.add('d-none');
        } else {
            // Find and show the quote cart icon (inside the loop like Odoo does)
            const quoteCartLi = document.querySelector('li.o_wsale_my_quote');
            if (quoteCartLi) {
                quoteCartLi.classList.remove('d-none');
            }
            cartQuantityElement.classList.remove('d-none');
            cartQuantityElement.classList.add('o_mycart_zoom_animation');
            setTimeout(() => {
                cartQuantityElement.textContent = quantity;
                cartQuantityElement.classList.remove('o_mycart_zoom_animation');
            }, 300);
        }
    }
    
    // Also handle case where there are no badge elements yet but we need to show the icon
    if (quantity > 0) {
        const quoteCartLis = document.querySelectorAll('li.o_wsale_my_quote');
        quoteCartLis.forEach(li => li.classList.remove('d-none'));
    } else {
        const quoteCartLis = document.querySelectorAll('li.o_wsale_my_quote');
        quoteCartLis.forEach(li => li.classList.add('d-none'));
    }
}

export default {
    getQuoteCartQuantity: getQuoteCartQuantity,
    setQuoteCartQuantity: setQuoteCartQuantity,
    updateQuoteCartNavBar: updateQuoteCartNavBar,
};
