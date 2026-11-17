{
    'name': 'School Management Library',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Library catalogue, members, loans and returns',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['mail', 'school_core', 'school_student', 'school_teacher'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_library_rules.xml',
        'data/ir_sequence_data.xml',
        'views/book_views.xml',
        'views/member_views.xml',
        'views/loan_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/library_demo.xml',
    ],
    'installable': True,
    'application': False,
}
