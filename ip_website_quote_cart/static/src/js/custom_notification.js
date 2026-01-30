/** @odoo-module **/

import { CartNotification } from "@website_sale/js/notification/cart_notification/cart_notification";
import { AddToCartNotification } from "@website_sale/js/notification/add_to_cart_notification/add_to_cart_notification";

// Extend CartNotification props to include is_quote
CartNotification.props = {
    ...CartNotification.props,
    is_quote: { type: Boolean, optional: true },
};

// Extend AddToCartNotification props to include is_quote
AddToCartNotification.props = {
    ...AddToCartNotification.props,
    is_quote: { type: Boolean, optional: true },
};