from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchoolAdmission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = cls.env['school.school'].create({
            'name': 'Admission Test School',
            'code': 'ATS',
        })
        cls.year = cls.env['school.academic.year'].create({
            'name': '2026/2027',
            'date_start': '2026-09-01',
            'date_end': '2027-06-30',
            'school_id': cls.school.id,
            'is_current': True,
        })
        cls.stage = cls.env['school.stage'].create({
            'name': 'Primary',
            'school_id': cls.school.id,
        })
        cls.grade = cls.env['school.grade'].create({
            'name': 'Grade 1',
            'stage_id': cls.stage.id,
        })
        cls.section = cls.env['school.section'].create({
            'name': 'A',
            'grade_id': cls.grade.id,
            'academic_year_id': cls.year.id,
        })

    def _create_application(self, **overrides):
        values = {
            'applicant_name': 'Yara Khaled',
            'gender': 'female',
            'birth_date': '2019-04-12',
            'national_id': 'NID-998877',
            'guardian_name': 'Khaled Samir',
            'guardian_relation': 'father',
            'guardian_phone': '+201000000001',
            'guardian_email': 'khaled.samir@example.com',
            'school_id': self.school.id,
            'academic_year_id': self.year.id,
            'grade_id': self.grade.id,
            'section_id': self.section.id,
        }
        values.update(overrides)
        return self.env['school.admission'].create(values)

    def test_application_number_is_generated(self):
        application = self._create_application()
        self.assertTrue(application.name.startswith('APP/'))

    def test_enroll_creates_student_and_guardian(self):
        application = self._create_application()
        application.action_submit()
        application.action_accept()
        application.action_enroll()

        self.assertEqual(application.state, 'enrolled')
        self.assertTrue(application.student_id)
        self.assertTrue(application.student_id.reference.startswith('STU/'))
        self.assertEqual(application.student_id.school_id, self.school)
        self.assertEqual(application.student_id.name, 'Yara Khaled')

        link = application.student_id.guardian_ids
        self.assertEqual(len(link), 1)
        self.assertTrue(link.is_primary)
        self.assertTrue(link.partner_id.is_school_guardian)
        self.assertEqual(link.partner_id.name, 'Khaled Samir')

        self.assertEqual(application.enrollment_id.state, 'active')
        self.assertEqual(application.enrollment_id.section_id, self.section)
        self.assertEqual(self.section.student_count, 1)

    def test_cannot_enroll_unaccepted_application(self):
        application = self._create_application()
        with self.assertRaises(UserError):
            application.action_enroll()
        self.assertFalse(application.student_id)

    def test_full_admission_workflow(self):
        application = self._create_application()
        application.action_submit()
        self.assertEqual(application.state, 'submitted')
        application.action_start_review()
        self.assertEqual(application.state, 'under_review')
        with self.assertRaises(UserError):
            application.action_schedule_interview()
        application.interview_date = '2026-11-20 10:00:00'
        application.action_schedule_interview()
        self.assertEqual(application.state, 'interview')
        application.action_accept()
        self.assertEqual(application.state, 'accepted')

        action = application.action_enroll()
        self.assertEqual(action['res_model'], 'school.student')
        self.assertEqual(action['res_id'], application.student_id.id)
        self.assertEqual(application.state, 'enrolled')
        self.assertEqual(application.student_id.state, 'active')

        application.action_reset_draft()
        self.assertEqual(application.state, 'draft')
        self.assertFalse(application.student_id)
        self.assertFalse(application.enrollment_id)

    def test_waitlist_and_reject(self):
        waitlisted = self._create_application()
        waitlisted.action_submit()
        waitlisted.action_waitlist()
        self.assertEqual(waitlisted.state, 'waitlisted')
        waitlisted.action_reset_draft()
        self.assertEqual(waitlisted.state, 'draft')

        rejected = self._create_application(applicant_name='Rana Adel')
        rejected.action_submit()
        rejected.action_reject()
        self.assertEqual(rejected.state, 'rejected')
        self.assertFalse(rejected.student_id)

    def test_submit_twice_is_rejected(self):
        application = self._create_application()
        application.action_submit()
        with self.assertRaises(UserError):
            application.action_submit()

    def test_enroll_requires_section(self):
        application = self._create_application(section_id=False)
        application.action_submit()
        application.action_accept()
        with self.assertRaises(UserError):
            application.action_enroll()
        self.assertFalse(application.student_id)

    def test_existing_guardian_partner_is_reused(self):
        partner = self.env['res.partner'].create({
            'name': 'Khaled Samir',
            'email': 'khaled.samir@example.com',
            'phone': '+201000000001',
        })
        application = self._create_application()
        application.action_submit()
        application.action_accept()
        application.action_enroll()
        self.assertEqual(application.student_id.guardian_ids.partner_id, partner)
        self.assertTrue(partner.is_school_guardian)

    def test_male_applicant_with_mother_guardian(self):
        application = self._create_application(
            applicant_name='Adam Khaled',
            gender='male',
            guardian_relation='mother',
            guardian_name='Hala Mostafa',
            guardian_email='hala.mostafa@example.com',
            guardian_phone='+201000000002',
        )
        application.action_submit()
        application.action_accept()
        application.action_enroll()
        self.assertEqual(application.student_id.gender, 'male')
        self.assertEqual(application.student_id.guardian_ids.relation, 'mother')

    def test_documents_complete(self):
        application = self._create_application()
        self.assertFalse(application.documents_complete)
        application.birth_certificate = True
        application.previous_report = True
        application.photos = True
        self.assertFalse(application.documents_complete)
        application.medical_report = True
        self.assertTrue(application.documents_complete)
