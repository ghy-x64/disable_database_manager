from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    database_manager_whitelist = fields.Char("Database manager whitelist")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        v_database_manager_whitelist = ICPSudo.get_param('disable_database_manager.database_manager_whitelist')
        res.update(
            database_manager_whitelist=v_database_manager_whitelist,
        )
        return res
    
    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        ICPSudo.set_param('disable_database_manager.database_manager_whitelist', self.database_manager_whitelist)

