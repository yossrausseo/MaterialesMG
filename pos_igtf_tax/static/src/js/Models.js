/** @odoo-module **/

import { Orderline, Order, Product, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { roundDecimals as round_di} from "@web/core/utils/numbers";

patch(Product.prototype, {
    get isIgtfProduct() {
        const { x_igtf_product_id } = this.pos.config;

        return (x_igtf_product_id)
            ? x_igtf_product_id[0] === this.id
            : false;
    }
});

patch(Payment.prototype, {
    get isForeignExchange() {
        return this.payment_method.x_is_foreign_exchange;
    },

   

    set_amount(value){
        var igtf_antes = this.order.x_igtf_amount;
        if(value == this.order.get_due()){
            this.order.assert_editable();
            this.amount = round_di(parseFloat(value) || 0, this.pos.currency.decimal_places);

        }else{
            if(value != igtf_antes){
                if(this.isForeignExchange){
                    //super.set_amount(value * (1/this.pos.config.show_currency_rate));
                    value = value * (1/this.pos.config.show_currency_rate)
                    this.order.assert_editable();
                    this.amount = round_di(parseFloat(value) || 0, this.pos.currency.decimal_places);
                }else{
                    //super.set_amount(value);
                    this.order.assert_editable();
                    this.amount = round_di(parseFloat(value) || 0, this.pos.currency.decimal_places);

                }
            }
        }
        const igtfProduct = this.pos.config.x_igtf_product_id;
        if(!(igtfProduct || igtfProduct?.length)) return;
        if(!this.isForeignExchange) return;
        if(value == igtf_antes) return;
        this.order.removeIGTF();

        const price = this.order.x_igtf_amount;

        this.order.add_product(this.pos.db.product_by_id[igtfProduct[0]], {
            quantity: 1,
            price,
            lst_price: price,
        });
    }
});

patch(Orderline.prototype, {
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.x_is_igtf_line = json.x_is_igtf_line;
    },
    export_as_JSON() {
        const result = super.export_as_JSON(...arguments);
        result.x_is_igtf_line = this.x_is_igtf_line;
        return result;
    },
    export_for_printing() {
        super.export_for_printing(...arguments);
        json.x_is_igtf_line =  this.x_is_igtf_line;
        return json;
      },
});

patch(Order.prototype, {
    /*
    get x_igtf_amount() {
        // 1. Calcular IGTF sobre pagos en divisa
        let igtf_monto = this.paymentlines
            .filter(p => p.isForeignExchange && p.amount > 0)
            .map(({ amount, payment_method: { x_igtf_percentage } }) => 
                amount * (x_igtf_percentage / 100))
            .reduce((prev, current) => prev + current, 0);

        // 2. Calcular total base (sin IGTF)
        let total = this.orderlines
            .filter(p => !p.x_is_igtf_line)
            .map(p => p.get_price_with_tax())
            .reduce((prev, current) => prev + current, 0);

        // 3. Sumar paquetes si existen
        let total_packs = this.orderlines
            .filter(p => !p.x_is_igtf_line)
            .flatMap(e => e.selected_product_list || [])
            .filter(e => typeof e === 'object' && e.price_unit != 0)
            .map(e => e.price_unit * e.qty)
            .reduce((prev, current) => prev + current, 0);

        total += total_packs;

        // 4. Calcular máximo permitido (3% del total)
        let max_igtf = total * 0.03;
        
        // 5. Usar el menor valor entre cálculo y máximo
        const final_igtf = Math.min(igtf_monto, max_igtf);
        
        console.log("[IGTF] Monto calculado:", igtf_monto, 
                   "| Máximo permitido:", max_igtf, 
                   "| IGTF a aplicar:", final_igtf);
                   
        return round_di(final_igtf, this.pos.currency.decimal_places);
    },
    */
    get x_igtf_amount() {
        // 1. Calcular el total base SIN incluir el IGTF
        const total_base = this.get_base_total_without_igtf();
        
        // 2. Calcular el monto ya cubierto por pagos que NO son en divisas
        const pagos_no_divisas = this.paymentlines
            .filter(p => !p.isForeignExchange && p.amount > 0)
            .reduce((sum, p) => sum + p.amount, 0);
        
        // 3. Calcular el saldo restante que puede ser cubierto con divisas
        const saldo_por_cubrir = Math.max(0, total_base - pagos_no_divisas);
        
        // 4. Calcular IGTF solo sobre la parte de los pagos en divisa que cubre el saldo
        let igtf_monto = 0;
        let saldo_cubierto_divisas = 0;
        
        this.paymentlines
            .filter(p => p.isForeignExchange && p.amount > 0)
            .forEach((payment) => {
                const monto_disponible = saldo_por_cubrir - saldo_cubierto_divisas;
                const monto_aplicable = Math.min(payment.amount, monto_disponible);
                
                if (monto_aplicable > 0) {
                    igtf_monto += monto_aplicable * (payment.payment_method.x_igtf_percentage / 100);
                    saldo_cubierto_divisas += monto_aplicable;
                }
            });

        // 5. Calcular máximo permitido (3% del total base)
        const max_igtf = total_base * 0.03;
        
        // 6. Usar el menor valor entre cálculo y máximo
        const final_igtf = Math.min(igtf_monto, max_igtf);
        
        console.log("[IGTF DEBUG]",
                   "\nTotal base:", total_base,
                   "\nPagos no divisas:", pagos_no_divisas,
                   "\nSaldo por cubrir:", saldo_por_cubrir,
                   "\nMonto IGTF calculado:", igtf_monto, 
                   "\nMáximo IGTF permitido:", max_igtf, 
                   "\nIGTF final:", final_igtf,
                   "\nSaldo cubierto por divisas:", saldo_cubierto_divisas);
                   
        return round_di(final_igtf, this.pos.currency.decimal_places);
    },

    get_base_total_without_igtf() {
        // Calcular total sin incluir líneas de IGTF
        let total = this.orderlines
            .filter(p => !p.x_is_igtf_line)
            .map(p => p.get_price_with_tax())
            .reduce((prev, current) => prev + current, 0);

        // Sumar paquetes si existen
        let total_packs = this.orderlines
            .filter(p => !p.x_is_igtf_line)
            .flatMap(e => e.selected_product_list || [])
            .filter(e => typeof e === 'object' && e.price_unit != 0)
            .map(e => e.price_unit * e.qty)
            .reduce((prev, current) => prev + current, 0);

        return total + total_packs;
    },
    /*get x_igtf_amount() {
        var igtf_monto = this.paymentlines
            .filter((p) => p.isForeignExchange)
            .map(({ amount, payment_method: { x_igtf_percentage } }) => amount * (x_igtf_percentage / 100))
            .reduce((prev, current) => prev + current, 0);
        // monto total de  todas las lineas sin el igtf
        var total = this.orderlines.filter((p) => !p.x_is_igtf_line).map((p) => p.get_price_with_tax()).reduce((prev, current) => prev + current, 0);

        let total_packs = this.orderlines.filter((p) => !p.x_is_igtf_line)
                       .flatMap(e=>e.selected_product_list)
                       .flatMap(e=>e)
                       .filter(e=>typeof(e) === 'object' && e.price_unit != 0)
           .map(e=>e.price_unit * e.qty)
           .reduce((prev, current) => prev + current, 0)

        total += total_packs;

        //maximo igtf
        var max_igtf = total * 0.03;
        //verifica que el monto no sea mayor al total
        if(igtf_monto > max_igtf){
            igtf_monto = max_igtf;
        }
        // console.log("total_dolares",total);
        // console.log("this",this);
        // console.log("igtf_monto",igtf_monto);
        // console.log("max_igtf",max_igtf);
        return parseFloat(max_igtf);
    },*/

    removeIGTF() {
        this.orderlines
            .filter(({ x_is_igtf_line }) => x_is_igtf_line)
            // .forEach((line) => this.remove_orderline(line));
            .forEach((line) => this.removeOrderline(line));
    },

    set_orderline_options(orderline, options) {
        super.set_orderline_options(orderline, options);
        orderline.x_is_igtf_line = orderline.product.isIgtfProduct;
    },
});