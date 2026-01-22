# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Legacy field - kept for backward compatibility
    website_request_quote = fields.Boolean(
        string="Website Enable Quote",
        related="website_id.website_request_quote",
        readonly=False,
    )
