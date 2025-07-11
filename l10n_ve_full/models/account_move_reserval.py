# -*- coding: utf-8 -*-

from odoo import models, _, fields


class AccountMoveReversalInherit(models.TransientModel):
    _inherit = 'account.move.reversal'

    nro_ctrl = fields.Char(
        'Número de Control', size=32,
        help="Número utilizado para gestionar facturas preimpresas, por ley "
             "Necesito poner aquí este número para poder declarar"
             "Informes fiscales correctamente.", store=True)
    supplier_invoice_number = fields.Char(
        string='Número de factura del proveedor', size=64,
        store=True)

    def reverse_moves(self, is_modify=False):
        # Asegurarse de que el método padre esté disponible
        if hasattr(super(), 'reverse_moves'):
            # Si es un método del padre, llamarlo primero
            result = super().reverse_moves()
            if result:
                return result

        # Obtener el contexto de la operación
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])

        # Seleccionar los movimientos a revertir
        if active_model == 'account.move' and active_ids:
            moves = self.env['account.move'].browse(active_ids)
        else:
            moves = self.move_id

        # Preparar valores por defecto para la reversión
        default_values_list = []
        for move in moves:
            default_values = self._prepare_default_reversal(move)
            
            # Agregar información personalizada
            if self.supplier_invoice_number:
                default_values['supplier_invoice_number'] = self.supplier_invoice_number
            if self.nro_ctrl:
                default_values['nro_ctrl'] = self.nro_ctrl
            
            default_values_list.append(default_values)

        # Realizar la reversión de movimientos
        new_moves = moves._reverse_moves(default_values_list, cancel=is_modify)

        # Manejo de movimientos posteados
        if new_moves.state != 'draft':
            try:
                new_moves.already_posted_iva()
            except AttributeError:
                # Método no existe, continuar sin él
                pass

        # Crear acción de redireccionamiento
        action = {
            'name': _('Reverse Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
        }

        if len(new_moves) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': new_moves.id,
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', new_moves.ids)],
            })

        return action