{
    'name': 'Dashboard Suite Purchase',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Purchasing dashboards for Dashboard Suite',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['dashboard_suite_core', 'purchase'],
    'data': [
        'data/purchase_dashboards.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
}
