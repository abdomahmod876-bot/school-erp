{
    'name': 'Dashboard Suite Sales',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Sales KPIs, targets and a predefined sales dashboard',
    'author': 'Dashboard Suite',
    'license': 'LGPL-3',
    'depends': ['dashboard_suite_core', 'sale_management'],
    'data': [
        'security/dashboard_suite_sales_rules.xml',
        'security/ir.model.access.csv',
        'views/sales_target_views.xml',
        'data/sales_dashboards.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
}
