{
    'name': 'School Management Exams',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Exam schedules and per-student results',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['mail', 'school_admission', 'school_academic', 'school_student', 'school_teacher'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_exam_rules.xml',
        'views/exam_views.xml',
        'views/exam_result_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/exam_demo.xml',
    ],
    'installable': True,
    'application': False,
}
