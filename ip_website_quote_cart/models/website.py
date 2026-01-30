# -*- coding: utf-8 -*-

from odoo import models, SUPERUSER_ID, fields
from odoo.http import request


class Website(models.Model):
    _inherit = 'website'

    # Legacy field - kept for backward compatibility
    website_request_quote = fields.Boolean(default=True)

    def update_quote_context(self):
        # context = self._context.copy()
        context = self.env.context.copy()
        context.update({
            'is_quote_order': True
        })
        return context

    def sale_reset(self):
        if self.env.context and self.env.context.get('is_quote_order'):
            # Only reset quote cart - don't touch normal cart
            request.session.pop('quote_order_id', None)
            request.session.pop('quote_cart_quantity', None)
        else:
            # Call parent for normal cart reset
            super(Website, self).sale_reset()

    def _prepare_sale_order_values(self, partner_sudo):
        res = super(Website, self)._prepare_sale_order_values(partner_sudo)
        res.update({
            'is_quote': True if self.env.context.get('is_quote_order') else False
        })
        return res

    def sale_get_quote_order(self, force_create=False):
        """ Return the current sales order after mofications specified by params.

        :param bool force_create: Create sales order if not already existing

        :returns: current cart, as a sudoed `sale.order` recordset (might be empty)
        """
        self.ensure_one()

        self = self.with_company(self.company_id)
        SaleOrder = self.env['sale.order'].sudo()

        quote_order_id = request.session.get('quote_order_id')

        if quote_order_id:
            quote_order_sudo = SaleOrder.browse(quote_order_id).exists()
        elif self.env.user and not self.env.user._is_public():
            quote_order_sudo = self.env.user.partner_id.last_website_qo_id
            if quote_order_sudo:
                available_pricelists = self.get_pricelist_available()
                so_pricelist_sudo = quote_order_sudo.pricelist_id
                if so_pricelist_sudo and so_pricelist_sudo not in available_pricelists:
                    # Do not reload the cart of this user last visit
                    # if the cart uses a pricelist no longer available.
                    quote_order_sudo = SaleOrder
                else:
                    # Do not reload the cart of this user last visit
                    # if the Fiscal Position has changed.
                    fpos = quote_order_sudo.env['account.fiscal.position'].with_company(
                        quote_order_sudo.company_id
                    )._get_fiscal_position(
                        quote_order_sudo.partner_id,
                        delivery=quote_order_sudo.partner_shipping_id
                    )
                    if fpos.id != quote_order_sudo.fiscal_position_id.id:
                        quote_order_sudo = SaleOrder
        else:
            quote_order_sudo = SaleOrder

        # Ignore the current order if a payment has been initiated. We don't want to retrieve the
        # cart and allow the user to update it when the payment is about to confirm it.
        if quote_order_sudo and quote_order_sudo.get_portal_last_transaction().state in (
            'pending', 'authorized', 'done'
        ):
            quote_order_sudo = None

        if not (quote_order_sudo or force_create):
            # Do not create a SO record unless needed
            if request.session.get('quote_order_id'):
                request.session.pop('quote_order_id')
                request.session.pop('quote_cart_quantity', None)
            return self.env['sale.order']

        partner_sudo = self.env.user.partner_id

        # cart creation was requested
        if not quote_order_sudo:
            so_data = self._prepare_sale_order_values(partner_sudo)
            quote_order_sudo = SaleOrder.with_user(SUPERUSER_ID).create(so_data)

            request.session['quote_order_id'] = quote_order_sudo.id
            request.session['quote_cart_quantity'] = quote_order_sudo.cart_quantity
            # The order was created with SUPERUSER_ID, revert back to request user.
            return quote_order_sudo.with_user(self.env.user).sudo()

        # Existing Cart:
        #   * For logged user
        #   * In session, for specified partner

        # case when user emptied the cart
        if not request.session.get('quote_order_id'):
            request.session['quote_order_id'] = quote_order_sudo.id
            request.session['quote_cart_quantity'] = quote_order_sudo.cart_quantity

        # check for change of partner_id ie after signup
        if partner_sudo.id not in (quote_order_sudo.partner_id.id, self.partner_id.id):
            quote_order_sudo._update_address(partner_sudo.id, ['partner_id'])

        return quote_order_sudo
