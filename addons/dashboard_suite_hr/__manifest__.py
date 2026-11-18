{
    'name': 'Dashboard Suite HR',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Employee and department dashboards for Dashboard Suite',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['dashboard_suite_core', 'hr'],
    'data': [
        'data/hr_dashboards.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
}
