# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID
from odoo.tools import convert_file


def post_init_hook(env):
    """Load optional module integrations if those modules are installed."""
    
    # Enable quote button on product tiles by default
    # Add o_wsale_products_opt_has_quote to all websites' shop design classes
    websites = env['website'].search([])
    for website in websites:
        current_classes = website.shop_opt_products_design_classes or ''
        if 'o_wsale_products_opt_has_quote' not in current_classes:
            website.shop_opt_products_design_classes = current_classes + ' o_wsale_products_opt_has_quote'
    
    # Check if website_sale_comparison is installed
    comparison_module = env['ir.module.module'].search([
        ('name', '=', 'website_sale_comparison'),
        ('state', '=', 'installed')
    ], limit=1)
    
    if comparison_module:
        convert_file(
            env,
            'ip_website_quote_cart',
            'views/template_comparison.xml',
            idref={},
            mode='init',
            noupdate=False
        )
    
    # Check if website_sale_wishlist is installed
    wishlist_module = env['ir.module.module'].search([
        ('name', '=', 'website_sale_wishlist'),
        ('state', '=', 'installed')
    ], limit=1)
    
    if wishlist_module:
        convert_file(
            env,
            'ip_website_quote_cart',
            'views/template_wishlist.xml',
            idref={},
            mode='init',
            noupdate=False
        )
