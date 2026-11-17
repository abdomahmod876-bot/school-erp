from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolExam(models.Model):
    _name = 'school.exam'
    _inherit = ['school.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Exam'
    _order = 'date_start desc, name'

    name = fields.Char(required=True, tracking=True)
    exam_type = fields.Selection(
        selection=[
            ('quiz', 'Quiz'),
            ('monthly', 'Monthly Test'),
            ('midterm', 'Midterm Exam'),
            ('final', 'Final Exam'),
            ('practical', 'Practical Exam'),
        ],
        required=True, default='midterm', tracking=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', string='Academic Year', required=True,
        tracking=True, domain="[('school_id', '=', school_id)]")
    section_ids = fields.Many2many(
        'school.section', 'school_exam_section_rel', 'exam_id', 'section_id',
        string='Sections',
        domain="[('academic_year_id', '=', academic_year_id)]")
    date_start = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Results Published'),
        ],
        required=True, default='draft', tracking=True, index=True)
    schedule_ids = fields.One2many(
        'school.exam.schedule', 'exam_id', string='Schedule')
    schedule_count = fields.Integer(compute='_compute_stats')
    result_count = fields.Integer(compute='_compute_stats')
    average_percent = fields.Float(compute='_compute_stats', digits=(5, 2))
    note = fields.Text()

    @api.depends('schedule_ids', 'schedule_ids.result_ids.percentage')
    def _compute_stats(self):
        for exam in self:
            results = exam.schedule_ids.result_ids
            exam.schedule_count = len(exam.schedule_ids)
            exam.result_count = len(results)
            percentages = results.mapped('percentage')
            exam.average_percent = (
                sum(percentages) / len(percentages) if percentages else 0.0)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for exam in self:
            if exam.date_end < exam.date_start:
                raise ValidationError(
                    _('The exam end date must be on or after the start date.'))

    @api.constrains('section_ids', 'academic_year_id', 'school_id')
    def _check_sections(self):
        for exam in self:
            for section in exam.section_ids:
                if section.school_id != exam.school_id:
                    raise ValidationError(
                        _('The section %(section)s does not belong to the school of the exam.',
                          section=section.display_name))
                if section.academic_year_id != exam.academic_year_id:
                    raise ValidationError(
                        _('The section %(section)s belongs to another academic year.',
                          section=section.display_name))

    def action_generate_results(self):
        for exam in self:
            if exam.state != 'draft':
                raise UserError(
                    _('Reset the exam to draft before generating results.'))
            if not exam.section_ids:
                raise UserError(
                    _('Select at least one section before generating results.'))
            if not exam.schedule_ids:
                raise UserError(
                    _('Add the exam schedule before generating results.'))
            enrollments = self.env['school.enrollment'].search([
                ('section_id', 'in', exam.section_ids.ids),
                ('academic_year_id', '=', exam.academic_year_id.id),
                ('state', '=', 'active'),
            ])
            if not enrollments:
                raise UserError(
                    _('There are no active enrollments in the selected sections.'))
            for schedule in exam.schedule_ids:
                loaded = schedule.result_ids.student_id
                commands = [
                    (0, 0, {'student_id': enrollment.student_id.id})
                    for enrollment in enrollments
                    if enrollment.student_id not in loaded
                ]
                if commands:
                    schedule.write({'result_ids': commands})

    def action_publish_results(self):
        for exam in self:
            if not exam.schedule_ids:
                raise UserError(
                    _('Add the exam schedule before publishing results.'))
            if exam.schedule_ids.filtered(lambda schedule: not schedule.result_ids):
                raise UserError(
                    _('Enter results for every scheduled subject before publishing.'))
        self.write({'state': 'published'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SchoolSection(models.Model):
    _inherit = 'school.section'

    exam_ids = fields.Many2many(
        'school.exam', 'school_exam_section_rel', 'section_id', 'exam_id',
        string='Exams')
