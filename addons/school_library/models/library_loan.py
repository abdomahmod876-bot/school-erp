from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolLibraryLoan(models.Model):
    _name = 'school.library.loan'
    _description = 'Library Loan'
    _order = 'loan_date desc, id desc'

    reference = fields.Char(
        string='Loan No.', default='New', copy=False,
        readonly=True, index=True)
    book_id = fields.Many2one(
        'school.library.book', string='Book', required=True,
        ondelete='restrict', index=True)
    member_id = fields.Many2one(
        'school.library.member', string='Member', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id), ('active', '=', True)]")
    school_id = fields.Many2one(
        'school.school', related='book_id.school_id',
        store=True, readonly=True, index=True)
    loan_date = fields.Date(
        required=True, default=fields.Date.context_today, index=True)
    due_date = fields.Date(
        required=True,
        default=lambda self: fields.Date.add(
            fields.Date.context_today(self), days=14))
    return_date = fields.Date()
    state = fields.Selection(
        selection=[
            ('borrowed', 'Borrowed'),
            ('returned', 'Returned'),
            ('lost', 'Lost'),
        ],
        required=True, default='borrowed', index=True)
    late_days = fields.Integer(compute='_compute_late_days')
    note = fields.Text()

    _reference_uniq = models.Constraint(
        'UNIQUE(reference)',
        'The loan number must be unique.',
    )

    @api.depends('state', 'due_date', 'return_date')
    def _compute_late_days(self):
        today = fields.Date.context_today(self)
        for loan in self:
            if not loan.due_date:
                loan.late_days = 0
                continue
            end_date = loan.return_date or (
                today if loan.state == 'borrowed' else False)
            if not end_date or end_date <= loan.due_date:
                loan.late_days = 0
            else:
                loan.late_days = (end_date - loan.due_date).days

    @api.constrains('loan_date', 'due_date', 'return_date')
    def _check_dates(self):
        for loan in self:
            if loan.due_date < loan.loan_date:
                raise ValidationError(_(
                    'The due date must be on or after the loan date.'))
            if loan.return_date and loan.return_date < loan.loan_date:
                raise ValidationError(_(
                    'The return date cannot be before the loan date.'))

    @api.constrains('member_id', 'book_id')
    def _check_member_school(self):
        for loan in self:
            if loan.member_id.school_id != loan.school_id:
                raise ValidationError(_(
                    'The member and the book must belong to the same school.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('school.library.loan')
                    or 'New')
        loans = super().create(vals_list)
        for loan in loans.filtered(lambda loan: loan.state == 'borrowed'):
            book = loan.book_id
            on_loan = len(book.loan_ids.filtered(
                lambda other: other.state in ('borrowed', 'lost')))
            if on_loan > book.copies_total:
                raise UserError(_(
                    'No copy of %(book)s is available: %(total)s copies, '
                    '%(on_loan)s on loan.',
                    book=book.name,
                    total=book.copies_total,
                    on_loan=on_loan))
        return loans

    def action_return(self):
        for loan in self:
            if loan.state != 'borrowed':
                raise UserError(_('Only borrowed loans can be returned.'))
        self.write({
            'state': 'returned',
            'return_date': fields.Date.context_today(self),
        })

    def action_mark_lost(self):
        for loan in self:
            if loan.state != 'borrowed':
                raise UserError(_('Only borrowed loans can be marked as lost.'))
        self.write({'state': 'lost'})

    def action_reset_borrowed(self):
        for loan in self:
            if loan.state == 'lost':
                raise UserError(_(
                    'A lost copy must be received back before resetting the loan.'))
        self.write({'state': 'borrowed', 'return_date': False})
