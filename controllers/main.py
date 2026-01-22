# -*- coding: utf-8 -*-

import json
import logging
from werkzeug.exceptions import Forbidden, NotFound
from datetime import timedelta, datetime
from odoo import fields, http, models, _
from odoo.http import request, route
from odoo import _lt
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.sale.controllers.portal import CustomerPortal as CustomerPortalSale
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.website.controllers.form import WebsiteForm
from odoo.addons.base.models.ir_qweb_fields import nl2br_enclose
from odoo.tools import lazy, str2bool, clean_context
from odoo.exceptions import AccessError, MissingError, ValidationError
_logger = logging.getLogger(__name__)


class QuoteCartForm(WebsiteForm):
    """Handle form submissions for quote cart extra info page."""

    @route('/website/form/shop.quote.order', type='http', auth="public", methods=['POST'], website=True)
    def website_form_quote_order(self, **kwargs):
        """Process quote cart extra info form - similar to shop.sale.order but for quote cart."""
        model_record = request.env.ref('sale.model_sale_order').sudo()
        try:
            data = self.extract_data(model_record, kwargs)
        except ValidationError as e:
            return json.dumps({'error_fields': e.args[0]})

        # Get the quote order instead of normal cart
        order_sudo = request.website.with_context(
            request.website.update_quote_context()
        ).sale_get_quote_order()
        
        if not order_sudo:
            return json.dumps({'error': "No quote order found; please add a product to your quote cart."})

        # Write standard fields to the order
        if data['record']:
            order_sudo.write(data['record'])

        # Log custom fields as a message in chatter
        if data['custom']:
            order_sudo._message_log(
                body=nl2br_enclose(data['custom'], 'p'),
                message_type='comment',
            )

        # Attach any uploaded files
        if data['attachments']:
            self.insert_attachment(model_record, order_sudo.id, data['attachments'])

        return json.dumps({'id': order_sudo.id})


class WebsiteSale(WebsiteSale):
    @route('/shop/update_address', type='jsonrpc', auth='public', website=True)
    def shop_update_address(self, partner_id, address_type='billing', **kw):
        """Override to support quote checkout - uses quote order when quote_checkout is active."""
        partner_id = int(partner_id)
        
        # Check if we're in quote checkout mode by looking at the referer or session
        is_quote_checkout = kw.get('quote_cart') or '/shop/quote/' in request.httprequest.referrer if request.httprequest.referrer else False
        
        if is_quote_checkout:
            order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        else:
            order_sudo = request.cart
            
        if not order_sudo:
            return

        ResPartner = request.env['res.partner'].sudo()
        partner_sudo = ResPartner.browse(partner_id).exists()
        children = ResPartner._search([
            ('id', 'child_of', order_sudo.partner_id.commercial_partner_id.id),
            ('type', 'in', ('invoice', 'delivery', 'other')),
        ])
        if (partner_sudo != order_sudo.partner_id and partner_sudo != order_sudo.partner_id.commercial_partner_id and partner_sudo.id not in children):
            raise Forbidden()
        partner_fnames = set()
        if (address_type == 'billing' and partner_sudo != order_sudo.partner_invoice_id):
            partner_fnames.add('partner_invoice_id')
        elif (address_type == 'delivery' and partner_sudo != order_sudo.partner_shipping_id):
            partner_fnames.add('partner_shipping_id')
        order_sudo._update_address(partner_id, partner_fnames)

    @route('/shop/delivery_methods', type='jsonrpc', auth='public', website=True)
    def shop_delivery_methods(self):
        """Override to support quote checkout - returns empty for quote orders (no delivery needed)."""
        # Check if we're in quote checkout mode
        is_quote_checkout = '/shop/quote/' in request.httprequest.referrer if request.httprequest.referrer else False
        
        if is_quote_checkout:
            # Quote checkout doesn't need delivery methods - return empty template
            order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
            if order_sudo:
                values = {
                    'delivery_methods': [],
                    'selected_dm_id': False,
                    'order': order_sudo,
                }
                return request.env['ir.ui.view']._render_template('website_sale.delivery_form', values)
            return ''
        
        # Normal checkout - call parent method
        return super().shop_delivery_methods()

    @http.route(['/shop/quote/update'], type='jsonrpc', auth='public', methods=['POST'], website=True, csrf=False)
    def update_quote_cart(self, line_id, quantity, product_id=None, **kwargs):

        order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order(force_create=1)
        quantity = int(quantity)  # Do not allow float values in ecommerce by default
        IrUiView = request.env['ir.ui.view']

        # This method must be only called from the cart page BUT in some advanced logic
        # eg. website_sale_loyalty, a cart line could be a temporary record without id.
        # In this case, the line_id must be found out through the given product id.
        if not line_id:
            line_id = order_sudo.order_line.filtered(
                lambda sol: sol.product_id.id == product_id
            )[:1].id

        values = order_sudo._cart_update_line_quantity(line_id, quantity, **kwargs)

        values['quote_cart_quantity'] = order_sudo.cart_quantity
        request.session['quote_cart_quantity'] = order_sudo.cart_quantity
        values['cart_ready'] = order_sudo._is_cart_ready()
        values['amount'] = order_sudo.amount_total
        values['is_quote_cart'] = 'is_quote_cart'

        values['ip_website_quote_cart.cart_lines'] = IrUiView._render_template(
            'ip_website_quote_cart.cart_lines', {
                'website_sale_order': order_sudo,
                'date': fields.Date.today(),
                'suggested_products': order_sudo._cart_accessories()
            }
        )
        values['website_sale.total'] = IrUiView._render_template(
            'website_sale.total', {
                'website_sale_order': order_sudo,
            }
        )
        values['website_sale.quick_reorder_history'] = IrUiView._render_template(
            'website_sale.quick_reorder_history', {
                'website_sale_order': order_sudo,
                **self._prepare_order_history(),
            }
        )
        return values

    @http.route(['/shop/quote/cart/update_json'], type='jsonrpc', auth="public", methods=['POST'], website=True, csrf=False)
    def quote_cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True, **kwargs):
        """This route is called when changing quantity from the cart or adding
        a product from the wishlist."""
        order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order(force_create=1)

        if order.state != 'draft':
            request.website.with_context(request.website.update_quote_context()).sale_reset()
            return {}

        value = order.with_context(skip_cart_verification=True)._cart_add(product_id=product_id, quantity=add_qty, **kwargs)
        request.session['quote_cart_quantity'] = order.cart_quantity

        if not order.cart_quantity:
            request.website.with_context(request.website.update_quote_context()).sale_reset()
            return value

        value['quote_cart_quantity'] = order.cart_quantity
        value['is_quote_cart'] = True

        # Get the line that was just added/updated for notification
        added_line_ids = value.get('line_id') or value.get('line_ids', [])
        if isinstance(added_line_ids, int):
            added_line_ids = [added_line_ids]
        
        # Build notification info for quote cart
        if added_line_ids:
            lines = order.order_line.filtered(lambda l: l.id in added_line_ids)
            value['notification_info'] = {
                'currency_id': order.currency_id.id,
                'lines': [
                    {
                        'id': line.id,
                        'image_url': request.website.image_url(line.product_id, 'image_128'),
                        'quantity': line.product_uom_qty,
                        'name': line.name_short or line.product_id.name,
                        'combination_name': line._get_combination_name() if hasattr(line, '_get_combination_name') else '',
                        'price_total': 0,  # Set to 0 so price is hidden for quote cart
                        'hide_price': True,  # Flag to hide price in notification
                    } for line in lines
                ],
            }

        value['ip_website_quote_cart.cart_lines'] = request.env['ir.ui.view']._render_template("ip_website_quote_cart.cart_lines", {
            'website_sale_order': order,
            'date': fields.Date.today(),
            'suggested_products': order._cart_accessories(),
        })
        value['website_sale.short_cart_summary'] = request.env['ir.ui.view']._render_template("ip_website_quote_cart.short_cart_summary", {
            'website_sale_order': order,
        })
        if not display:
            return value
        return value

    @http.route(['/shop/quote/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def quote_cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """This route is called when adding a product to cart (no options)."""
        sale_order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['quote_order_id'] = None
            sale_order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))
        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values
        )
        request.session['quote_cart_quantity'] = sale_order.cart_quantity

        if kw.get('express'):
            return request.redirect("/shop/checkout?express=1")
        return request.redirect("/shop/quote/cart")

    @http.route(['/shop/quote/cart'], type='http', auth="public", website=True, sitemap=False)
    def quote_cart(self, access_token=None, revive='', **post):
        """
        Main cart management + abandoned cart revival
        access_token: Abandoned cart SO access token
        revive: Revival method when abandoned cart. Can be 'merge' or 'squash'add_to_cart
        """
        order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        if order and order.state != 'draft':
            request.session['quote_order_id'] = None
            order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        values = {}
        request.session['quote_cart_quantity'] = order.cart_quantity if order else 0

        if access_token:
            abandoned_order = request.env['sale.order'].sudo().search([('access_token', '=', access_token)], limit=1)
            if not abandoned_order:  # wrong token (or SO has been deleted)
                raise NotFound()
            if abandoned_order.state != 'draft':  # abandoned cart already finished
                values.update({'abandoned_proceed': True})
            elif revive == 'squash' or (revive == 'merge' and not request.session.get('quote_order_id')):  # restore old cart or merge with unexistant
                request.session['quote_order_id'] = abandoned_order.id
                return request.redirect('/shop/quote/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['quote_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session.get('quote_order_id'):  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})

        values.update({
            'website_sale_order': order,
            'date': fields.Date.today(),
            'suggested_products': [],
        })
        if order:
            order.order_line.filtered(lambda sol: sol.product_id and not sol.product_id.active).unlink()
            values['suggested_products'] = order._cart_accessories()

        if post.get('type') == 'popover':
            values.update({
                'is_quote_popover': True
            })
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("website_sale.cart_popover", values, headers={'Cache-Control': 'no-cache'})

        return request.render("ip_website_quote_cart.quote_cart", values)

    def _prepare_checkout_page_values(self, order_sudo, **kwargs):
        res = super()._prepare_checkout_page_values(order_sudo, **kwargs)

        if order_sudo.is_quote:
            res['address_url'] = '/shop/quote/address'
        else:
            res['address_url'] = '/shop/address'

        return res

    @route(
        ['/shop/checkout', '/shop/<string:quote_cart>/checkout'], type='http', methods=['GET'], auth='public', website=True, sitemap=False
    )
    def shop_checkout(self, try_skip_step=None, quote_cart=None, **query_params):
        """ Display the checkout page.

        :param str try_skip_step: Whether the user should immediately be redirected to the next step
                                                if no additional information (i.e., address or delivery method) is
                                                required on the checkout page. 'true' or 'false'.
        :param str quote_cart: Path parameter to indicate quote cart checkout.
        :param dict query_params: The additional query string parameters.
        :return: The rendered checkout page.
        :rtype: str
        """
        try_skip_step = str2bool(try_skip_step or 'false')
        is_quote_checkout = quote_cart == 'quote'
        order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order() if is_quote_checkout else request.cart
        request.session['sale_last_order_id'] = order_sudo.id

        redirection = self.quote_checkout_check_address(order_sudo) if is_quote_checkout else self._check_cart_and_addresses(order_sudo)
        if redirection:
            return redirection

        checkout_page_values = self._prepare_checkout_page_values(order_sudo, **query_params)
        checkout_page_values.update({
            'quote_checkout': is_quote_checkout,
            'website_sale_order': order_sudo
        })

        can_skip_delivery = True  # Delivery is only needed for deliverable products.
        if order_sudo._has_deliverable_products():
            can_skip_delivery = False
            available_dms = order_sudo._get_delivery_methods()
            checkout_page_values['delivery_methods'] = available_dms
            if delivery_method := order_sudo._get_preferred_delivery_method(available_dms):
                rate = delivery_method.rate_shipment(order_sudo)
                if (
                    not order_sudo.carrier_id
                    or not rate.get('success')
                    or order_sudo.amount_delivery != rate['price']
                ):
                    order_sudo._set_delivery_method(delivery_method, rate=rate)

        checkout_page_values.update(
            request.website._get_checkout_step_values()
        )
        if try_skip_step and can_skip_delivery:
            return request.redirect(
                checkout_page_values['next_website_checkout_step_href']
            )

        return request.render('website_sale.checkout', checkout_page_values)

    @http.route(['/shop/address', '/shop/<string:quote_cart>/address'], type='http', methods=['GET'], auth='public', website=True, sitemap=False)
    def shop_address(self, partner_id=None, address_type='billing', use_delivery_as_billing=None, quote_cart=None, **query_params):
        partner_id = partner_id and int(partner_id)
        use_delivery_as_billing = str2bool(use_delivery_as_billing or 'false')
        is_quote_order = quote_cart == 'quote'
        order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order() if is_quote_order else request.cart

        if redirection := self._check_cart(order_sudo):
            return redirection

        # Retrieve the partner whose address to update, if any, and its address type.
        partner_sudo, address_type = self._prepare_address_update(
            order_sudo, partner_id=partner_id and int(partner_id), address_type=address_type
        )

        use_delivery_as_billing = str2bool(use_delivery_as_billing or 'false')
        if partner_sudo:  # If editing an existing partner.
            use_delivery_as_billing = (
                partner_sudo == order_sudo.partner_shipping_id == order_sudo.partner_invoice_id
            )

        # Render the address form.
        address_form_values = self._prepare_address_form_values(
            partner_sudo,
            address_type=address_type,
            order_sudo=order_sudo,
            use_delivery_as_billing=use_delivery_as_billing,
            is_quote_order=is_quote_order,
            **query_params
        )
        address_form_values.update(
            request.website._get_checkout_step_values()
        )
        # address_form_values = serialize_values(address_form_values)

        # print(json.dumps(address_form_values, indent=2))
        return request.render('website_sale.address', address_form_values)

    def _prepare_address_form_values(self, *args, callback='', order_sudo=False, is_quote_order=False, **kwargs):

        rendering_values = super()._prepare_address_form_values(
            *args, order_sudo=order_sudo, callback=callback, **kwargs
        )
        rendering_values['is_quote_order'] = is_quote_order
        rendering_values['quote_checkout'] = is_quote_order  # For checkout_layout template
        return rendering_values

    @route(['/shop/address/submit', '/shop/quote/address'], type='http', methods=['POST'], auth='public', website=True, sitemap=False)
    def shop_address_submit(self, partner_id=None, address_type='billing', use_delivery_as_billing=None, callback=None, **form_data):
        # order_sudo = request.cart
        order_sudo = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order() if form_data and form_data.get('quote_cart') else request.cart

        if redirection := self._check_cart(order_sudo):
            return json.dumps({'redirectUrl': redirection.location})

        # Retrieve the partner whose address to update, if any, and its address type.
        partner_sudo, address_type = self._prepare_address_update(
            order_sudo, partner_id=partner_id and int(partner_id), address_type=address_type
        )

        is_new_address = not partner_sudo
        is_quote = form_data.get('quote_cart') or order_sudo.is_quote
        
        if is_new_address or order_sudo.only_services:
            if is_quote:
                callback = callback or '/shop/quote/checkout?try_skip_step=true'
            else:
                callback = callback or '/shop/checkout?try_skip_step=true'
        elif is_quote:
            callback = '/shop/quote/checkout'
        else:
            callback = callback or '/shop/checkout'

        partner_sudo, feedback_dict = self._create_or_update_address(
            partner_sudo,
            address_type=address_type,
            use_delivery_as_billing=use_delivery_as_billing,
            callback=callback,
            order_sudo=order_sudo,
            **form_data
        )

        if feedback_dict.get('invalid_fields'):
            return json.dumps(feedback_dict)

        is_anonymous_cart = order_sudo._is_anonymous_cart()
        is_main_address = is_anonymous_cart or order_sudo.partner_id.id == partner_sudo.id
        partner_fnames = set()
        if is_main_address:  # Main customer address updated.
            partner_fnames.add('partner_id')  # Force the re-computation of partner-based fields.

        if address_type == 'billing':
            partner_fnames.add('partner_invoice_id')
            if is_new_address and order_sudo.only_services:
                # The delivery address is required to make the order.
                partner_fnames.add('partner_shipping_id')
        elif address_type == 'delivery':
            partner_fnames.add('partner_shipping_id')
            if use_delivery_as_billing:
                partner_fnames.add('partner_invoice_id')

        order_sudo._update_address(partner_sudo.id, partner_fnames)

        if order_sudo._is_anonymous_cart():
            # Unsubscribe the public partner if the cart was previously anonymous.
            order_sudo.message_unsubscribe(order_sudo.website_id.partner_id.ids)

        return json.dumps(feedback_dict)

    def quote_checkout_check_address(self, order):
        # billing_fields_required = self._get_mandatory_billing_address_fields(order.partner_id.country_id.id)
        billing_fields_required = self._get_mandatory_billing_address_fields(order.partner_id.country_id)
        if not all(order.partner_id.read(billing_fields_required)[0].values()):
            return request.redirect('/shop/quote/address?partner_id=%d' % order.partner_id.id)

        # shipping_fields_required = self._get_mandatory_delivery_address_fields(order.partner_shipping_id.country_id.id)
        shipping_fields_required = self._get_mandatory_delivery_address_fields(order.partner_shipping_id.country_id)
        if not all(order.partner_shipping_id.read(shipping_fields_required)[0].values()):
            return request.redirect('/shop/quote/address?partner_id=%d' % order.partner_shipping_id.id)

    @http.route(['/shop/quote/extra_info'], type='http', auth="public", website=True, sitemap=False)
    def quote_extra_info(self, **post):
        """Display the extra info page for quote cart - similar to /shop/extra_info for normal cart."""
        order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        
        if not order or not order.order_line:
            return request.redirect('/shop/quote/cart')
        if order.state != 'draft':
            request.session['quote_order_id'] = None
            return request.redirect('/shop')
        
        # Check address is filled
        redirection = self.quote_checkout_check_address(order)
        open_editor = request.params.get('open_editor') == 'true'
        if not open_editor and redirection:
            return redirection
        
        values = {
            'website_sale_order': order,
            'post': post,
            'escape': lambda x: x.replace("'", r"\'"),
            'partner': order.partner_id.id,
            'order': order,
            'is_quote_order': True,
        }
        
        return request.render("ip_website_quote_cart.quote_extra_info", values)

    @http.route(['/shop/quote/submit'], type='http', auth="public", website=True, sitemap=False)
    def quote_submite_order(self, **post):
        order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        if order and not order.order_line:
            return request.redirect('/shop/quote/cart')
        if not order or order.state != 'draft':
            request.session['quote_order_id'] = None
            return request.redirect('/shop')
        redirection = self.quote_checkout_check_address(order)
        if redirection:
            return redirection
        order._compute_fiscal_position_id()
        # order.order_line._compute_tax_id()
        request.session['last_order_quote_id'] = request.session.get('quote_order_id')
        request.session['quote_order_id'] = None
        request.session['quote_cart_quantity'] = 0
        order.is_quote_req_submit = True
        return request.redirect("/shop/quote/submit/%s" % (order.id))

    @http.route(['/shop/quote/submit/<int:so_id>'], type='http', auth="public", website=True, sitemap=False)
    def quote_submite_send(self, so_id=None, **post):
        if so_id and request.session.get('last_order_quote_id') and so_id == request.session.get('last_order_quote_id'):
            env = request.env['sale.order'].sudo()
            domain = [('id', '=', so_id)]
            order = env.search(domain, limit=1)
        else:
            order = request.website.with_context(request.website.update_quote_context()).sale_get_quote_order()
        values = {
            'website_sale_order': order,
            'order': order,
            'order_reference': order.name,
        }
        request.session['quote_cart_quantity'] = 0
        return request.render("ip_website_quote_cart.qt_thanks_page", values)


class CustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        SaleOrder = request.env['sale.order'].sudo()
        if 'requested_quotation_count' in counters:
            values['requested_quotation_count'] = SaleOrder.search_count([
                # ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
                ('partner_id', '=', partner.id),
                ('state', 'in', ['draft', 'sent', 'cancel']),
                ('is_quote_req_submit', '=', True)
            ]) if SaleOrder.check_access_rights('read', raise_exception=False) else 0

        return values

    #
    # Quotations and Sales Orders
    #

    @http.route(['/my/requested_quotes', '/my/requested_quotes/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_requested_quotes(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        SaleOrder = request.env['sale.order'].sudo()

        domain = [
            # ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['draft', 'sent', 'cancel']),
            ('is_quote_req_submit', '=', True)
        ]

        searchbar_sortings = {
            'date': {'label': _('Order Date'), 'order': 'date_order desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'stage': {'label': _('Stage'), 'order': 'state'},
        }

        # default sortby order
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # count for pager
        quotation_count = SaleOrder.search_count(domain)
        # make pager
        pager = portal_pager(
            url="/my/requested_quotes",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=quotation_count,
            page=page,
            step=self._items_per_page
        )
        # search the count to display, according to the pager data
        quotations = SaleOrder.search(domain, order=sort_order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_quotations_history'] = quotations.ids[:100]

        values.update({
            'date': date_begin,
            'quotations': quotations.sudo(),
            'page_name': 'requested_quote',
            'pager': pager,
            'default_url': '/my/requested_quotes',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("ip_website_quote_cart.portal_my_requested_quotations", values)


class CustomerPortalSale(CustomerPortalSale):
    def _prepare_sale_portal_rendering_values(self, page=1, date_begin=None, date_end=None, sortby=None, quotation_page=False, **kwargs):
        SaleOrder = request.env['sale.order']

        if not sortby:
            sortby = 'date'

        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()

        if quotation_page:
            url = "/my/quotes"
            domain = self._prepare_quotations_domain(partner)
            domain += [('validity_date','>=',fields.Date.today() - timedelta(days=10))]
        else:
            url = "/my/orders"
            domain = self._prepare_orders_domain(partner)

        searchbar_sortings = self._get_sale_searchbar_sortings()

        sort_order = searchbar_sortings[sortby]['order']

        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        pager_values = portal_pager(
            url=url,
            total=SaleOrder.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
        )
        orders = SaleOrder.search(domain, order=sort_order, limit=self._items_per_page, offset=pager_values['offset'])
        values.update({
            'date': date_begin,
            'quotations': orders.sudo() if quotation_page else SaleOrder,
            'orders': orders.sudo() if not quotation_page else SaleOrder,
            'page_name': 'quote' if quotation_page else 'order',
            'pager': pager_values,
            'default_url': url,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })

        return values

    def _prepare_quotations_domain(self, partner):
        return [
            ('message_partner_ids', 'child_of', [partner.commercial_partner_id.id]),
            ('state', '=', 'sent'),
            ('validity_date','>=',fields.Date.today() - timedelta(days=10))
        ]

    @http.route(['/my/quotes/<int:order_id>/decline'], type='http', auth="public", methods=['POST'], website=True)
    def portal_quote_decline(self, order_id, access_token=None, decline_message=None, **kwargs):
        try:
            order_sudo = self._document_check_access('sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if decline_message:
            order_sudo._action_cancel()
            # The currency is manually cached while in a sudoed environment to prevent an
            # AccessError. The state of the Sales Order is a dependency of
            # `untaxed_amount_to_invoice`, which is a monetary field. They require the currency to
            # ensure the values are saved in the correct format. However, the currency cannot be
            # read directly during the flush due to access rights, necessitating manual caching.
            order_sudo.order_line.currency_id

            order_sudo.message_post(
                author_id=(
                    order_sudo.partner_id.id
                    if request.env.user._is_public()
                    else request.env.user.partner_id.id
                ),
                body=decline_message,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
            redirect_url = order_sudo.get_portal_url()
        else:
            redirect_url = order_sudo.get_portal_url(query_string="&message=cant_reject")

        return request.redirect(redirect_url)
