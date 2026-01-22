# -*- coding: utf-8 -*-

{
    'name': 'Website Quote Cart',
    'version': '19.0.0.0',
    'summary': 'An additional cart to request quotations directly from the eShop',
    'description': "",
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
    'price': 40,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
}
