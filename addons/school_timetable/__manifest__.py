{
    'name': 'School Management Timetable',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Class periods and section timetables with conflict detection',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['school_core', 'school_academic', 'school_teacher'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_timetable_rules.xml',
        'views/period_views.xml',
        'views/timetable_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/timetable_demo.xml',
    ],
    'installable': True,
    'application': False,
}
