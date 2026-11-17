{
    'name': 'School Management Attendance',
    'version': '19.0.1.0.0',
    'category': 'Education',
    'summary': 'Daily and per-period attendance registers for sections',
    'author': 'School ERP Team',
    'license': 'LGPL-3',
    'depends': ['school_admission', 'school_timetable', 'school_teacher'],
    'data': [
        'security/ir.model.access.csv',
        'security/school_attendance_rules.xml',
        'views/attendance_views.xml',
        'views/menus.xml',
    ],
    'demo': [
        'demo/attendance_demo.xml',
    ],
    'installable': True,
    'application': False,
}
