# Copyright 2015 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    'name': "Disable database manager",
    'summary': """Disable database manager""",
    'description': """
        Disable database manager""",
    'author': 'GHY',
    'category': 'Apps',
    'version': '1.0',
    'depends': [
        'base_setup',
        'web',
    ],
    'data': [
        'views/res_config_settings_view.xml',
    ],
    'installable': True,
}
