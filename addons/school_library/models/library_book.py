from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolLibraryBook(models.Model):
    _name = 'school.library.book'
    _inherit = ['school.mixin', 'mail.thread']
    _description = 'Library Book'
    _order = 'name'

    name = fields.Char(required=True, tracking=True, index=True)
    isbn = fields.Char(string='ISBN', index=True)
    author = fields.Char()
    publisher = fields.Char()
    category = fields.Selection(
        selection=[
            ('textbook', 'Textbook'),
            ('fiction', 'Fiction'),
            ('reference', 'Reference'),
            ('periodical', 'Periodical'),
            ('other', 'Other'),
        ],
        required=True, default='textbook')
    edition = fields.Char()
    publication_year = fields.Integer()
    shelf = fields.Char(help='Shelf or section location in the library.')
    copies_total = fields.Integer(required=True, default=1)
    loan_ids = fields.One2many(
        'school.library.loan', 'book_id', string='Loans')
    loan_count = fields.Integer(compute='_compute_copies')
    copies_on_loan = fields.Integer(compute='_compute_copies')
    copies_available = fields.Integer(compute='_compute_copies')
    note = fields.Text()
    active = fields.Boolean(default=True)

    _isbn_uniq = models.Constraint(
        'UNIQUE(isbn)',
        'The ISBN must be unique.',
    )
    _copies_check = models.Constraint(
        'CHECK(copies_total >= 1)',
        'A book must have at least one copy.',
    )

    @api.depends('copies_total', 'loan_ids.state')
    def _compute_copies(self):
        for book in self:
            loans = book.loan_ids
            on_loan = len(loans.filtered(
                lambda loan: loan.state in ('borrowed', 'lost')))
            book.loan_count = len(loans)
            book.copies_on_loan = on_loan
            book.copies_available = book.copies_total - on_loan

    @api.constrains('copies_total')
    def _check_copies_not_below_loans(self):
        for book in self:
            on_loan = len(book.loan_ids.filtered(
                lambda loan: loan.state in ('borrowed', 'lost')))
            if book.copies_total < on_loan:
                raise ValidationError(_(
                    'The total copies of %(book)s cannot be lower than the '
                    '%(count)s copies currently on loan.',
                    book=book.name,
                    count=on_loan))
