{
    'name': 'School Management Admission',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Admission applications, acceptance workflow and student enrollment',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['mail', 'school_student', 'school_academic'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_admission_rules.xml',
        'data/ir_sequence_data.xml',
        'views/admission_views.xml',
        'views/enrollment_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/admission_demo.xml',
    ],
    'installable': True,
    'application': False,
}
