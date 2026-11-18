{
    'name': 'Dashboard Suite Inventory',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Stock and transfer dashboards for Dashboard Suite',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['dashboard_suite_core', 'stock'],
    'data': [
        'data/inventory_dashboards.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
}
