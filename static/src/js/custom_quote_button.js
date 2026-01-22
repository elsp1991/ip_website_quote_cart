/** @odoo-module **/

import {
    ProductConfiguratorDialog
} from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { rpc } from "@web/core/network/rpc";
import { patch } from '@web/core/utils/patch';
import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";
import "@website/libs/zoomodoo/zoomodoo";
import { serializeDateTime } from "@web/core/l10n/dates";
import { useSubEnv } from '@odoo/owl';

const { DateTime } = luxon;
import wSaleUtils from "@website_sale/js/website_sale_utils";

// Patch ProductConfiguratorDialog to allow adding products with zero price to quote cart
patch(ProductConfiguratorDialog.prototype, {
    setup() {
        super.setup(...arguments);
        
        // Add isQuoteCart to the environment so child components can access it
        useSubEnv({
            isQuoteCart: this.props.options?.is_quote_cart ?? false,
        });
    },
    
    /**
     * Override canBeSold to allow adding products with zero price to quote cart
     * when the request_quote feature is enabled.
     */
    canBeSold() {
        // If this is for quote cart, always allow adding regardless of price
        if (this.props.options?.is_quote_cart) {
            return true;
        }
        // Otherwise, use the standard behavior
        return super.canBeSold(...arguments);
    },
    
    /**
     * Override showShopButtons to hide default cart buttons when is_quote_cart is true.
     * Our custom quote buttons will be shown instead via the XML template.
     */
    showShopButtons() {
        // If this is for quote cart, hide the default shop buttons
        // (our custom quote buttons will be shown via the XML template)
        if (this.props.options?.is_quote_cart) {
            return false;
        }
        // Otherwise, use the standard behavior
        return super.showShopButtons(...arguments);
    },
    
    /**
     * Check whether to show the quote buttons in the dialog footer.
     */
    showQuoteButtons() {
        return this.props.isFrontend && !this.props.edit && this.props.options?.is_quote_cart;
    },
});

publicWidget.registry.mdProductShopPage = publicWidget.Widget.extend({
    selector: '#products_grid',
    events: {
        'click #product_add_to_cart_from_shop': '_onClickAddToQuoteFromProductsPage',
        'click .js_add_quote_grid': '_onClickAddToQuoteFromProductsPage',
    },
    /**
     * Hook to append additional props in overriding modules.
     *
     * @return {Object} The additional props.
     */
    _getAdditionalDialogProps() {
        return {};
    },

    showQuoteCartNotification: function (callService, props, options = {}) {
	    // Show the notification about the cart
	    if (props.lines) {
	        callService("cartNotificationService", "add", _t("Item(s) added to your cart"), {
	            lines: props.lines,
	            currency_id: props.currency_id,
	            is_quote: props.is_quote,
	            ...options,
	        });
	    }
	    if (props.warning) {
	        callService("cartNotificationService", "add", _t("Warning"), {
	            warning: props.warning,
	            ...options,
	        });
	    }
	},
	
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickAddToQuoteFromProductsPage: async function (ev) {
        const shouldShowProductConfiguratorQuote = await rpc(
            '/website_sale/should_show_product_configurator',
            {
                product_template_id: parseInt($($(ev.currentTarget).closest('div')).find("input[name=product_template_id]")[0].value),
                ptav_ids: [],
                is_product_configured: false,
            }
        )
        if (shouldShowProductConfiguratorQuote) {
            this.call('dialog', 'add', ProductConfiguratorDialog, {
                productTemplateId: parseInt($($(ev.currentTarget).closest('div')).find("input[name=product_template_id]")[0].value),
                ptavIds: [],
                customPtavs: [].map(
                    customPtav => ({
                        id: customPtav.custom_product_template_attribute_value_id,
                        value: customPtav.custom_value,
                    })
                ),
                quantity: 1,
                soDate: serializeDateTime(DateTime.now()),
                edit: false,
                isFrontend: true,
                options: {
                    isMainProductConfigurable: true,
                    showQuantity: true,
                    is_quote_cart: true,
                },
                save: async (mainProduct, optionalProducts, options) => {
                    // Add main product
		        var product_id = mainProduct.id
		        var qty = mainProduct.quantity
		        const params = {
	            product_id: parseInt(product_id),
	            add_qty: parseFloat(qty),
	        	};

                let data = await rpc("/shop/quote/cart/update_json", {
                    ...params,
                    display: false,
                    force_create: true,
                });

                // Add optional products
                for (const optionalProduct of optionalProducts) {
                    data = await rpc("/shop/quote/cart/update_json", {
                        product_id: optionalProduct.id,
                        add_qty: optionalProduct.quantity,
                        display: false,
                    });
                }
                
                // Mark data as quote cart and update UI
                data.is_quote_cart = 'is_quote_cart';
                wSaleUtils.updateCartNavBar(data);
                
                // Show notification
                if (data.notification_info && data.notification_info.lines) {
                    this.showQuoteCartNotification(this.call.bind(this), {
                        lines: data.notification_info.lines,
                        currency_id: data.notification_info.currency_id || 0,
                        is_quote: true,
                    });
                }
                
                // Navigate to quote cart if "Go to Quote" was clicked
                if (options && options.goToCart) {
                    window.location.href = '/shop/quote/cart';
                }
                },
                discard: () => {},
                ...this._getAdditionalDialogProps(),
            })
        }
        else{
            var product_id = $($(ev.currentTarget).closest('div')).find("input[name=product_id]")[0].value
            const params = {
                product_id: parseInt(product_id),
                add_qty: parseFloat(1),
            };
            const data = await rpc("/shop/quote/cart/update_json", {
                ...params,
                display: false,
                force_create: true,
            });

            // Mark data as quote cart and update UI
            data.is_quote_cart = 'is_quote_cart';
            wSaleUtils.updateCartNavBar(data);
            
            // Show notification
            if (data.notification_info && data.notification_info.lines) {
                this.showQuoteCartNotification(this.call.bind(this), {
                    lines: data.notification_info.lines,
                    currency_id: data.notification_info.currency_id || 0,
                    is_quote: true,
                });
            }
        }
    },
});