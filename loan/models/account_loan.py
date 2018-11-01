# Copyright 2018 Creu Blanca

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.exceptions import ValidationError

from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import numpy as np
import math

class AccountLoan(models.Model):
    _name = 'account.loan'
    _description = 'Prestamos'
    _inherit = [
        'mail.thread',
        'ir.needaction_mixin',
    ]

    states_loans = [
        ('draft', 'Borrador'),
        ('post', 'Aprobado'),
        ('paid', 'Pagado'),
        ('cancel', 'Cancelado'),
    ]

    name = fields.Char("Nombre")
    state = fields.Selection(states_loans, string="Estatus", default='draft')
    rate_id = fields.Many2one(required="True", comodel_name="rate.loan",string="Tarifa")
    line_ids = fields.One2many(
        comodel_name="account.loan.line",
        string="Lineas de prestamo",
        inverse_name='loan_id',
        copy=False,
    )
    amount = fields.Monetary(required="True",string="Monto a prestar")
    currency_id = fields.Many2one(comodel_name="res.currency",string="Moneda")
    partner_id = fields.Many2one(comodel_name="res.partner",string="Cliente")
    payments = fields.Integer(string="Cuotas")
    payment_amount = fields.Monetary(string="Cuota")
    start_date = fields.Date(string="Fecha inicial")


    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('account.loan') or '/'
        vals['name'] = seq
        res = super(AccountLoan, self).create(vals)
        return res

    @api.multi
    def compute_payment(self):
        if self.payments == 0:
            raise ValidationError("Debe seleccionar la cantidad de cuotas")
        else:
            self.payment_amount = -np.pmt(self.rate_id.rate/100,self.payments, self.amount)

    @api.multi
    def compute_lines(self):
        self.ensure_one()
        self.compute_payment()
        if self.state == 'draft':
            return self.compute_draft_lines()
        return self.compute_posted_lines()

    def new_line_vals(self, sequence, date, interest, payment):
        return {
            'loan_id': self.id,
            'number': sequence,
            'date': date,
            'interest': interest,
            'payment': payment,
            'dues': payment + interest,
            'rate': self.rate_id.rate,
            'currency_id': self.currency_id.id,
        }

    @api.multi
    def compute_draft_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        amount = self.amount

        if self.start_date:
            date = datetime.strptime(self.start_date, DF).date()
        else:
            date = datetime.today().date()

        if self.rate_id.type == 'daily':
            delta = relativedelta(days=1)
        elif self.rate_id.type == 'weekly':
            delta = relativedelta(weeks=1)
        elif self.rate_id.type == 'quincel':
            delta = relativedelta(weeks=2)
        elif self.rate_id.type == 'monthly':
            delta = relativedelta(months=1)
        elif self.rate_id.type == 'bimonthly':
            delta = relativedelta(months=2)

        for i in range(1, self.payments + 1):
            interest = amount * self.rate_id.rate/100
            payment = self.payment_amount - interest

            line = self.env['account.loan.line'].create(
                self.new_line_vals(i, date, interest, payment)
            )
            # line.check_amount()
            date += delta
            amount -= line.dues - line.interest
            line.total = amount


    @api.multi
    def post(self):
        self.state = 'post'
        for line in self.line_ids:
            line.ready = True

    @api.multi
    def cancel(self):
        self.state = 'cancel'


class AccountLoanLine(models.Model):
    _name = 'account.loan.line'
    _description = 'Cuotas'

    number = fields.Char(string="Numero")
    ready = fields.Boolean(string="Lista", default=False)
    date = fields.Date(string="Fecha")
    date_paid = fields.Date(string="Fecha de pago")
    rate = fields.Float(string="Tarifa", digits=(8, 2))
    loan_id = fields.Many2one('account.loan', string="Prestamo")
    dues = fields.Monetary(string="Cuota")
    payment = fields.Monetary(string="Abono")
    morse = fields.Monetary(string="Mora")
    currency_id = fields.Many2one(comodel_name="res.currency",string="Moneda")
    interest = fields.Monetary(string="Interes")
    total = fields.Monetary(string="Saldo Final")
    paid = fields.Boolean(string="Pagada")
    invoice_id = fields.Many2one("account.invoice", string="Factura")

    def pay_due(self):
        action = self.env.ref('loan.action_due_make_invoices').read()[0]
        # action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
        return action

    @api.multi
    def due_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        return self.env['report'].get_action(self, 'reporte_factura.payment_receipt_doc')

    def invoice_due(self):
        self.ensure_one()
        invoice_line_ids = []
        loan_prod = self.env['product.template'].search([('default_code', '=', 'loan')])
        morse_tmpl = self.env['product.template'].search([('default_code', '=', 'morse')])
        prod = self.env['product.product'].search([('product_tmpl_id', '=', loan_prod.id)])
        morse_prod = self.env['product.product'].search([('product_tmpl_id', '=', morse_tmpl.id)])
        invoice_line_ids.append((0, 0, {
            'product_id': prod.id,
            'name': prod.name,
            'price_unit': self.dues,
            'account_id': prod.property_account_income_id.id
        }))
        due_date = datetime.strptime(self.date, '%Y-%m-%d')
        today = datetime.today()
        if due_date < today:
            morse = self.dues * (self.loan_id.rate_id.morse/100)
            print morse
            times = (today - due_date).days
            if self.loan_id.rate_id.type == 'daily':
                times = times
            elif self.loan_id.rate_id.type == 'weekly':
                times = int(times/7)
            elif self.loan_id.rate_id.type == 'quincel':
                times = int(times/15)
            elif self.loan_id.rsate_id.type == 'monthly':
                times = int(times/30)
            elif self.loan_id.rate_id.type == 'bimonthly':
                times = int(times/60)

            print times
            morse_last = 0.0
            for time in range(times):
                morse_last += morse

            self.morse = morse_last
            if morse_last > 0.0 :
                invoice_line_ids.append((0, 0, {
                    'product_id': morse_prod.id,
                    'name': morse_prod.name,
                    'price_unit': morse_last,
                    'account_id': morse_prod.property_account_income_id.id
                }))
            else:
                pass

        journal_id = self.env['account.journal'].search([('code', '=', 'loan')])
        account_invoice_obj = self.env['account.invoice']
        vals = {
            'partner_id': self.loan_id.partner_id.id,
            'type': 'out_invoice',
            'journal_id': journal_id.id,
            'name': self.loan_id.name +" Cuota: "+ self.number,
            'invoice_line_ids': invoice_line_ids,
        }
        invoice_id = account_invoice_obj.create(vals)
        invoice_id.action_invoice_open()

        if invoice_id:
            self.paid = True
            self.date_paid = datetime.today()
            self.invoice_id = invoice_id.id
            action = self.env.ref('account.action_invoice_tree1').read()[0]
            action['domain'] = [['id', '=', invoice_id.id]]
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoice_id.id
            return action
        else:
            return {'type': 'ir.actions.act_window_close'}

class RateLoan(models.Model):
    _name = 'rate.loan'
    _description = 'Tarifas'
    _rec_name = 'name'

    types = [
        ('daily','Diario'),
        ('weekly', 'Semanal'),
        ('quincel', 'Quincenal'),
        ('monthly', 'Mensual'),
        ('bimonthly', 'Bimensual'),
    ]

    name = fields.Char(string="Nombre", required=True)
    type = fields.Selection(types, string="Tipo", required=True)
    rate = fields.Float(string="Tarifa", digits=(8, 2), required=True)
    morse = fields.Float("Mora")
