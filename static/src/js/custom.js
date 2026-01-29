/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from '@web/core/utils/patch';
import { patchDynamicContent } from '@web/public/utils';

import publicWidget from "@web/legacy/js/public/public_widget";
import VariantMixin from "@website_sale/js/variant_mixin";
import wSaleUtils from "@website_sale/js/website_sale_utils";
import wUtils from '@website/js/utils';
const cartHandlerMixin = wSaleUtils.cartHandlerMixin;
import { WebsiteSale } from "@website_sale/interactions/website_sale";
import { CartLine } from "@website_sale/interactions/cart_line";
import { Component } from "@odoo/owl";
import { browser } from '@web/core/browser/browser';
import { rpc } from "@web/core/network/rpc";
import { ProductConfiguratorDialog } from '@sale/js/product_configurator_dialog/product_configurator_dialog';
import { serializeDateTime } from "@web/core/l10n/dates";
import quoteCartUtils from '@ip_website_quote_cart/js/quote_cart_utils';

import "@website/libs/zoomodoo/zoomodoo";

const { DateTime } = luxon;

	const _superUpdateCartNavBar = wSaleUtils.updateCartNavBar;
	wSaleUtils.updateCartNavBar = function(data){
		// Only handle quote cart updates if explicitly marked
		if(data && data['is_quote_cart'] == 'is_quote_cart' && data.hasOwnProperty('quote_cart_quantity')){
			// Update quote cart quantity using utility function
			quoteCartUtils.updateQuoteCartNavBar(data.quote_cart_quantity);
			
			// Update quote cart lines if present
			if(data['ip_website_quote_cart.cart_lines'] != undefined){
				$(".quote_cart_lines").first().before(data['ip_website_quote_cart.cart_lines']).end().remove();
			}
		}
		else{
			// For everything else (normal cart), call the original function
			_superUpdateCartNavBar(data);
		}
	}
	patch(CartLine.prototype, {
	    async _changeQuantity(input) {
	    	if(input.dataset['cart_type'] == 'quote'){
	    		await this._chnageQuoteCarQuantiy(input);
	    	} else {
	    		return super._changeQuantity(input);
	    	}
	    },

	    async _chnageQuoteCarQuantiy(input) {

		    let quantity = parseInt(input.value || 0);
		    if (isNaN(quantity)) quantity = 1;

		    const lineId = parseInt(input.dataset.lineId);
		    const productId = parseInt(input.dataset.productId);

		    const data = await rpc('/shop/quote/update', {
		        line_id: lineId,
		        product_id: productId,
		        quantity: quantity,
		    });

		    // If cart empty
		    if (!data.quote_cart_quantity) {
		        return window.location = '/shop/quote/cart';
		    }

		    // Update UI
		    input.value = data.quantity;
		    document.querySelectorAll(`.js_quantity[data-line-id="${lineId}"]`)
		        .forEach(el => el.value = data.quantity);

		    const cart = this.el.closest('#shop_cart');
		    this.services['public.interactions'].stopInteractions(cart);
		    data.is_quote_cart = 'is_quote_cart';
		    wSaleUtils.updateCartNavBar(data);
		    this.services['public.interactions'].startInteractions(cart);

		    if (data.warning) {
		        wSaleUtils.showWarning(data.warning);
		    }
		}
	});

	patch(WebsiteSale.prototype, {

	    setup() {
	        super.setup();
	        patchDynamicContent(this.dynamicContent, {
	            '#add_to_quote_cart': { 't-on-click': this._onClickAddQuoteCalling.bind(this) },
	            '.js_add_to_quote_cart': { 't-on-click': this._onClickAddToQuoteCartSimple.bind(this) },
	        });
	    },

	    /**
	     * Handle click on "Add to Quote" button in comparison/wishlist pages
	     * @private
	     * @param {MouseEvent} ev
	     */
	    async _onClickAddToQuoteCartSimple(ev) {
	        ev.preventDefault();
	        ev.stopPropagation();
	        const button = ev.currentTarget;
	        const productId = parseInt(button.dataset.productProductId);
	        const productTemplateId = parseInt(button.dataset.productTemplateId);
	        
	        if (!productId || isNaN(productId)) {
	            console.error('Invalid product ID for Add to Quote');
	            return;
	        }
	        
	        try {
	            const data = await rpc('/shop/quote/cart/update_json', {
	                product_id: productId,
	                add_qty: 1,
	            });
	            
	            // Update navbar and show notification
	            if (data) {
	                this._updateQuoteCartUI(data);
	            }
	        } catch (error) {
	            console.error('Error adding to quote cart:', error);
	        }
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

		_onClickAddQuoteCalling(ev){
			const data = this._onClickAddQuote(ev)
		},

		/**
	     * @private
	     * @param {MouseEvent} ev
	     */
	    async _onClickAddQuote(ev){
	    	ev.preventDefault();
	    	await this._handleAddQuote(ev);
	    },

	    async _handleAddQuote(ev) {
	        const $this2 = $(ev.currentTarget).closest('.js_product');
	        const productTemplateId = parseInt($this2.find('input[name=product_template_id]').val());
	        const productId = parseInt($this2.find('input[name=product_id]').val());
	        
	        // Get the currently selected variant attributes from the product page
	        const containerEl = $this2[0].querySelector('.js_add_cart_variants');
	        const ptavIds = wSaleUtils.getSelectedAttributeValues(containerEl);
	        
	        // Check if product configurator should be shown (for optional products)
	        const shouldShowProductConfiguratorQuote = await rpc(
	            '/website_sale/should_show_product_configurator',
	            {
	                product_template_id: productTemplateId,
	                ptav_ids: ptavIds,
	                is_product_configured: true,
	            }
	        );

	        if (shouldShowProductConfiguratorQuote) {
	            // Show configurator dialog for optional products
	            this.services.dialog.add(ProductConfiguratorDialog, {
	                productTemplateId: productTemplateId,
	                ptavIds: ptavIds,
	                customPtavs: [],
	                quantity: parseFloat($this2.find('.css_quantity .quantity').val() || 1),
	                soDate: serializeDateTime(DateTime.now()),
	                edit: false,
	                isFrontend: true,
	                options: {
	                    isMainProductConfigurable: false,
	                    showQuantity: true,
	                    is_quote_cart: true,
	                },
	                save: async (mainProduct, optionalProducts, options) => {
	                    // Collect all notification lines
	                    let allNotificationLines = [];
	                    let currencyId = 0;
	                    
	                    // Add main product
	                    const params = {
	                        product_id: mainProduct.id,
	                        add_qty: mainProduct.quantity,
	                    };
	                    
	                    let data = await rpc("/shop/quote/cart/update_json", {
	                        ...params,
	                        display: false,
	                        force_create: true,
	                    });
	                    
	                    // Collect main product notification info
	                    if (data.notification_info && data.notification_info.lines) {
	                        allNotificationLines = allNotificationLines.concat(data.notification_info.lines);
	                        currencyId = data.notification_info.currency_id || currencyId;
	                    }

	                    // Add optional products
	                    for (const optionalProduct of optionalProducts) {
	                        data = await rpc("/shop/quote/cart/update_json", {
	                            product_id: optionalProduct.id,
	                            add_qty: optionalProduct.quantity,
	                            display: false,
	                        });
	                        
	                        // Collect optional product notification info
	                        if (data.notification_info && data.notification_info.lines) {
	                            allNotificationLines = allNotificationLines.concat(data.notification_info.lines);
	                            currencyId = data.notification_info.currency_id || currencyId;
	                        }
	                    }

	                    // Update UI with combined notification info
	                    data.notification_info = {
	                        lines: allNotificationLines,
	                        currency_id: currencyId,
	                    };
	                    this._updateQuoteCartUI(data);
	                    
	                    // Navigate to quote cart if "Go to Quote" was clicked
	                    if (options && options.goToCart) {
	                        window.location.href = '/shop/quote/cart';
	                    }
	                },
	                discard: () => {},
	            });
	        } else {
	            // Direct add to cart without configurator
	            const $this = $(ev.currentTarget).closest('div');
	            const qty = $this2.find('.css_quantity .quantity').val();

	            const params = {
	                product_id: productId,
	                add_qty: parseFloat(qty),
	            };

	            const data = await rpc("/shop/quote/cart/update_json", {
	                ...params,
	                display: false,
	                force_create: true,
	            });

	            this._updateQuoteCartUI(data);
	        }
	    },

	    _updateQuoteCartUI(data) {
	        // Mark as quote cart and update quote cart UI only
	        data.is_quote_cart = 'is_quote_cart';
	        wSaleUtils.updateCartNavBar(data);
	        
	        // Show notification if we have notification_info
	        if (data.notification_info && data.notification_info.lines) {
	            this.services.cartNotificationService.add('', {
	                lines: data.notification_info.lines,
	                currency_id: data.notification_info.currency_id || 0,
	                is_quote: true,
	            });
	        }
	    },

	});

	publicWidget.registry.websiteSaleQuoteCartLink = publicWidget.Widget.extend({
	    selector: '#top_menu a[href$="/shop/quote/cart"]',
	    events: {
	        'mouseenter': '_onMouseEnter',
	        'mouseleave': '_onMouseLeave',
	        'click': '_onClick',
	    },

	    /**
	     * @constructor
	     */
	    init: function () {
	        this._super.apply(this, arguments);
	        this._popoverQuoteRPC = null;
	    },
	    /**
	     * @override
	     */
	    start: function () {
	        this.$el.popover({
	            trigger: 'manual',
	            animation: true,
	            html: true,
	            title: function () {
	                return _t("My Quote Cart");
	            },
	            container: 'body',
	            placement: 'auto',
	            template: '<div class="popover myquotecart-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>'
	        });
	        return this._super.apply(this, arguments);
	    },

	    //--------------------------------------------------------------------------
	    // Handlers
	    //--------------------------------------------------------------------------

	    /**
	     * @private
	     * @param {Event} ev
	     */
	    _onMouseEnter: function (ev) {
        	let self = this;
	        self.hovered = true;
	        $(this.selector).not(ev.currentTarget).popover('hide');
	        let timeout = setTimeout(function () {
	            if (!self.hovered || $('.myquotecart-popover:visible').length) {
	                return;
	            }
	            self._popoverRPC = $.get("/shop/quote/cart", {
	                type: 'popover',
	            }).then(function (data) {
	                const popover = Popover.getInstance(self.$el[0]);
	                popover._config.content = data;
	                popover.setContent(popover.getTipElement());
	                self.$el.popover("show");
	                $('.popover').on('mouseleave', function () {
	                    self.$el.trigger('mouseleave');
	                });
	                // Update quote cart quantity from session storage
	                self.cartQty = quoteCartUtils.getQuoteCartQuantity();
	                self._updateCartQuantityText();
	            });
	        }, 300);
	    },
	    /**
	     * @private
	     * @param {Event} ev
	     */
	    _onMouseLeave: function (ev) {
	        var self = this;
	        setTimeout(function () {
	            if ($('.popover:hover').length) {
	                return;
	            }
	            if (!self.$el.is(':hover')) {
	               self.$el.popover('hide');
	            }
	        }, 1000);
	    },
	    /**
	     * @private
	     * @param {Event} ev
	     */
	    _onClick: function (ev) {
	        // When clicking on the cart link, prevent any popover to show up (by
	        // clearing the related setTimeout) and, if a popover rpc is ongoing,
	        // wait for it to be completed before going to the link's href. Indeed,
	        // going to that page may perform the same computation the popover rpc
	        // is already doing.

	        if (this._popoverQuoteRPC && this._popoverQuoteRPC.state() === 'pending') {
	            ev.preventDefault();
	            var href = ev.currentTarget.href;
	            this._popoverQuoteRPC.then(function () {
	                window.location.href = href;
	            });
	        }
	    },
	});
export default {
    websiteSaleCart: publicWidget.registry.websiteSaleCart,
};
