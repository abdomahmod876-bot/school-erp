{
    'name': 'Dashboard Suite CRM',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'CRM pipeline dashboards for Dashboard Suite',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['dashboard_suite_core', 'crm'],
    'data': [
        'data/crm_dashboards.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
}
