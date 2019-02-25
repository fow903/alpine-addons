# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _


class DueInvoice(models.TransientModel):
    _name = "due.invoice"

    morse = fields.Monetary(string="Mora")
    currency_id = fields.Many2one(comodel_name="res.currency", string="Moneda")
    cober_morse = fields.Boolean(string="Cobrar Mora",default=True)

    @api.model
    def default_get(self, fields_list):
        res = super(DueInvoice, self).default_get(fields_list)
        context = dict(self._context or {})
        due = self.env['account.loan.line'].browse(context.get('active_ids')[0])

        res['morse'] = due.get_morse()
        res['currency_id'] = due.currency_id.id
        return res

    @api.multi
    def action_invoice(self):
        context = dict(self._context or {})
        due = self.env['account.loan.line'].browse(context.get('active_ids')[0])
        return due.invoice_due(self.cober_morse)
