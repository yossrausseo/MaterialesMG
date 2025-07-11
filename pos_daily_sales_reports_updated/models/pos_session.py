from odoo import api, models

class DailySalesReport(models.AbstractModel):
    _name = 'report.pos_daily_sales_reports_updated.report_daily_sales'

    @api.model
    def _get_report_values(self, docids, data=None):
        sessions = self.env['pos.session'].browse(docids)
        return {
            'docs': sessions,
            'tax_today': sessions.tax_today,
        }
