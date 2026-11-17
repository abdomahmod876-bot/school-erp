from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SchoolExamSchedule(models.Model):
    _name = 'school.exam.schedule'
    _description = 'Exam Schedule Line'
    _rec_name = 'subject_id'
    _order = 'date, start_time'

    exam_id = fields.Many2one(
        'school.exam', string='Exam', required=True,
        ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', related='exam_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='exam_id.academic_year_id',
        store=True, readonly=True, index=True)
    subject_id = fields.Many2one(
        'school.subject', string='Subject', required=True,
        ondelete='restrict', index=True,
        domain="[('school_id', '=', school_id)]")
    teacher_id = fields.Many2one(
        'school.teacher', string='Invigilator', ondelete='restrict',
        domain="[('school_id', '=', school_id)]")
    date = fields.Date(required=True)
    start_time = fields.Float(string='Start', required=True)
    end_time = fields.Float(string='End', required=True)
    duration = fields.Float(compute='_compute_duration', string='Duration (Hours)')
    room = fields.Char()
    max_marks = fields.Float(default=100.0, required=True)
    pass_mark = fields.Float(default=50.0, required=True)
    result_ids = fields.One2many(
        'school.exam.result', 'schedule_id', string='Results')
    result_count = fields.Integer(compute='_compute_result_stats')
    average_percent = fields.Float(
        compute='_compute_result_stats', digits=(5, 2))

    _exam_subject_uniq = models.Constraint(
        'UNIQUE(exam_id, subject_id)',
        'The subject is already scheduled in this exam.',
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for line in self:
            line.duration = max(line.end_time - line.start_time, 0.0)

    @api.depends('result_ids.percentage')
    def _compute_result_stats(self):
        for line in self:
            percentages = line.result_ids.mapped('percentage')
            line.result_count = len(percentages)
            line.average_percent = (
                sum(percentages) / len(percentages) if percentages else 0.0)

    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for line in self:
            if line.end_time <= line.start_time:
                raise ValidationError(
                    _('The end time must be after the start time.'))

    @api.constrains('max_marks', 'pass_mark')
    def _check_marks(self):
        for line in self:
            if line.max_marks <= 0:
                raise ValidationError(
                    _('The maximum marks must be greater than zero.'))
            if line.pass_mark < 0 or line.pass_mark > line.max_marks:
                raise ValidationError(
                    _('The pass mark must be between zero and the maximum marks.'))

    @api.constrains('date', 'exam_id')
    def _check_date_in_exam(self):
        for line in self:
            if not line.date:
                continue
            if line.date < line.exam_id.date_start or line.date > line.exam_id.date_end:
                raise ValidationError(
                    _('The exam date must fall within the exam period.'))
