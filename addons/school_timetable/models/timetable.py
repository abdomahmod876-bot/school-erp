from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolTimetable(models.Model):
    _name = 'school.timetable'
    _description = 'Section Timetable'
    _order = 'academic_year_id desc, section_id'

    section_id = fields.Many2one(
        'school.section', string='Section', required=True,
        ondelete='cascade', index=True)
    school_id = fields.Many2one(
        'school.school', related='section_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='section_id.academic_year_id',
        store=True, readonly=True, index=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
        ],
        required=True, default='draft', index=True)
    line_ids = fields.One2many(
        'school.timetable.slot', 'timetable_id', string='Slots')
    slot_count = fields.Integer(compute='_compute_slot_count')
    note = fields.Text()

    _section_year_uniq = models.Constraint(
        'UNIQUE(section_id, academic_year_id)',
        'This section already has a timetable for the academic year.',
    )

    @api.depends('line_ids')
    def _compute_slot_count(self):
        for timetable in self:
            timetable.slot_count = len(timetable.line_ids)

    def action_publish(self):
        for timetable in self:
            if not timetable.line_ids:
                raise UserError(_('Add at least one slot before publishing the timetable.'))
        self.write({'state': 'published'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class SchoolTimetableSlot(models.Model):
    _name = 'school.timetable.slot'
    _description = 'Timetable Slot'
    _order = 'day_of_week, period_id'

    timetable_id = fields.Many2one(
        'school.timetable', string='Timetable', required=True,
        ondelete='cascade', index=True)
    section_id = fields.Many2one(
        'school.section', related='timetable_id.section_id',
        store=True, readonly=True, index=True)
    school_id = fields.Many2one(
        'school.school', related='timetable_id.school_id',
        store=True, readonly=True, index=True)
    academic_year_id = fields.Many2one(
        'school.academic.year', related='timetable_id.academic_year_id',
        store=True, readonly=True, index=True)
    day_of_week = fields.Selection(
        selection=[
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        required=True, default='0')
    period_id = fields.Many2one(
        'school.period', string='Period', required=True,
        ondelete='restrict', domain="[('school_id', '=', school_id)]")
    subject_id = fields.Many2one(
        'school.subject', string='Subject', required=True,
        ondelete='restrict', domain="[('school_id', '=', school_id)]")
    teacher_id = fields.Many2one(
        'school.teacher', string='Teacher', ondelete='restrict',
        domain="[('school_id', '=', school_id)]")
    room = fields.Char()

    _slot_uniq = models.Constraint(
        'UNIQUE(timetable_id, day_of_week, period_id)',
        'This period is already scheduled for the section on that day.',
    )

    @api.constrains('period_id', 'subject_id', 'teacher_id', 'timetable_id')
    def _check_records_school(self):
        for slot in self:
            timetable = slot.timetable_id
            if slot.period_id.school_id != timetable.school_id:
                raise ValidationError(_('The period does not belong to the timetable school.'))
            if slot.subject_id.school_id != timetable.school_id:
                raise ValidationError(_('The subject does not belong to the timetable school.'))
            if slot.teacher_id and slot.teacher_id.school_id != timetable.school_id:
                raise ValidationError(_('The teacher does not belong to the timetable school.'))
            if (slot.teacher_id and slot.teacher_id.subject_ids
                    and slot.subject_id not in slot.teacher_id.subject_ids):
                raise ValidationError(_(
                    'The teacher %(teacher)s is not assigned to the subject %(subject)s.',
                    teacher=slot.teacher_id.name,
                    subject=slot.subject_id.name))

    @api.constrains('teacher_id', 'day_of_week', 'period_id')
    def _check_teacher_conflict(self):
        for slot in self.filtered('teacher_id'):
            conflict = self.search([
                ('academic_year_id', '=', slot.academic_year_id.id),
                ('day_of_week', '=', slot.day_of_week),
                ('period_id', '=', slot.period_id.id),
                ('teacher_id', '=', slot.teacher_id.id),
                ('id', '!=', slot.id),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    'The teacher %(teacher)s is already scheduled on %(day)s, period %(period)s.',
                    teacher=slot.teacher_id.name,
                    day=dict(self._fields['day_of_week'].selection).get(slot.day_of_week),
                    period=slot.period_id.name))

    @api.constrains('room', 'day_of_week', 'period_id')
    def _check_room_conflict(self):
        for slot in self.filtered('room'):
            conflict = self.search([
                ('school_id', '=', slot.school_id.id),
                ('academic_year_id', '=', slot.academic_year_id.id),
                ('day_of_week', '=', slot.day_of_week),
                ('period_id', '=', slot.period_id.id),
                ('room', '=', slot.room),
                ('id', '!=', slot.id),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    'The room %(room)s is already used on %(day)s, period %(period)s.',
                    room=slot.room,
                    day=dict(self._fields['day_of_week'].selection).get(slot.day_of_week),
                    period=slot.period_id.name))


class SchoolTeacher(models.Model):
    _inherit = 'school.teacher'

    timetable_slot_ids = fields.One2many(
        'school.timetable.slot', 'teacher_id', string='Timetable Slots')
    weekly_hours = fields.Float(compute='_compute_weekly_hours')

    @api.depends(
        'timetable_slot_ids.period_id.start_time',
        'timetable_slot_ids.period_id.end_time')
    def _compute_weekly_hours(self):
        for teacher in self:
            teacher.weekly_hours = sum(
                slot.period_id.end_time - slot.period_id.start_time
                for slot in teacher.timetable_slot_ids)


class SchoolSection(models.Model):
    _inherit = 'school.section'

    timetable_ids = fields.One2many(
        'school.timetable', 'section_id', string='Timetables')
