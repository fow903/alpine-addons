# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _


class DueInvoice(models.TransientModel):
    _name = "due.invoice"

    @api.multi
    def action_invoice(self):
        context = dict(self._context or {})
        due = self.env['account.loan.line'].browse(context.get('active_ids')[0])
        return due.invoice_due()
