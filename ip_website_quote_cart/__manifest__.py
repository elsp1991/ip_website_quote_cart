# -*- coding: utf-8 -*-

{
    'name': 'Website Online Quotation System',
    'version': '19.0.0.3',
    'summary': 'Add a dedicated quotation cart to your website for B2B quote requests.',
    'description': """
Website Online Quotation System (Quote Cart)
=============================================

Add a dedicated quotation cart to your Odoo eCommerce store, allowing customers 
to request quotes for products instead of purchasing directly. Ideal for B2B 
businesses that don't want to share their prices publicly.

Key Features:
- Dedicated Quotation Cart separate from shopping cart
- Works with product variants and optional products
- Hide prices with prevent_zero_price_sale integration
- Integration with Sales module
- Similar look and feel to the normal cart
- Application description step in quotation process
- Wishlist and Comparison page integration
""",
    'category': 'Website/Website',
    'license': 'OPL-1',
    'support': 'ilias.patsiaouras@gmail.com',
    'author': 'Ilias Patsiaouras',
    'depends': ['website_sale', 'sale_management', 'website_sale_wishlist', 'website_sale_comparison'],
    'post_init_hook': 'post_init_hook',
    'data': [
        'data/mail_template_data.xml',
        'views/res_config_settings_views.xml',
        'views/views.xml',
        'views/template.xml',
        'views/template_wishlist.xml',
        'views/template_comparison.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'ip_website_quote_cart/static/src/js/quote_cart_utils.js',
            'ip_website_quote_cart/static/src/js/custom_quote_button.js',
            'ip_website_quote_cart/static/src/scss/custom.scss',
            'ip_website_quote_cart/static/src/js/custom.js',
            'ip_website_quote_cart/static/src/js/product_configurator_dialog.xml',
            'ip_website_quote_cart/static/src/js/product.xml',
            'ip_website_quote_cart/static/src/js/custom_notification.js',
            'ip_website_quote_cart/static/src/js/custom_notification.xml',
            'ip_website_quote_cart/static/src/js/custom_addtocart_notification.xml',
        ],
        'website.website_builder_assets': [
            'ip_website_quote_cart/static/src/website_builder/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'price': 135,
    'currency': 'EUR',
}
