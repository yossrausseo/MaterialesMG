/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosDB } from "@point_of_sale/app/store/db";
// import { producttemplatepopup } from "@bi_pos_product_template/app/products/producttemplatepopup"
// import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
// import { _t } from "@web/core/l10n/translation";
// import { PosCrossSaleProducts } from "@bi_pos_cross_selling/app/product/poscrossproduct";

patch(PosDB.prototype, {

    add_products(products) {
        var self = this;
           for(var i = 0, len = products.length; i < len; i++){
                if(products[i].default_code == 'bi_igtf'){
                    products[i].not_returnable = true;
                    self.igtf_product = products[i];
                }
           }
           super.add_products(products)
           // self._super(products)
        // var stored_categories = this.product_by_category_id;

        // if (!(products instanceof Array)) {
        //     products = [products];
        // }
        // for (var i = 0, len = products.length; i < len; i++) {
        //     var product = products[i];
        //     if (product.id in this.product_by_id) {
        //         continue;
        //     }
        //     if (product.available_in_pos) {
        //         var search_string = unaccent(this._product_search_string(product));
        //         const all_categ_ids = product.pos_categ_ids.length
        //             ? product.pos_categ_ids
        //             : [this.root_category_id];
        //         product.product_tmpl_id = product.product_tmpl_id[0];
        //         for (const categ_id of all_categ_ids) {
        //             if (!stored_categories[categ_id]) {
        //                 stored_categories[categ_id] = [];
        //             }
        //             stored_categories[categ_id].push(product.id);

        //             if (this.category_search_string[categ_id] === undefined) {
        //                 this.category_search_string[categ_id] = "";
        //             }
        //             this.category_search_string[categ_id] += search_string;

        //             var ancestors = this.get_category_ancestors_ids(categ_id) || [];

        //             for (var j = 0, jlen = ancestors.length; j < jlen; j++) {
        //                 var ancestor = ancestors[j];
        //                 if (!stored_categories[ancestor]) {
        //                     stored_categories[ancestor] = [];
        //                 }
        //                 stored_categories[ancestor].push(product.id);

        //                 if (this.category_search_string[ancestor] === undefined) {
        //                     this.category_search_string[ancestor] = "";
        //                 }
        //                 this.category_search_string[ancestor] += search_string;
        //             }
        //         }
        //     }
        //     this.product_by_id[product.id] = product;
        //     if (product.barcode && product.active) {
        //         this.product_by_barcode[product.barcode] = product;
        //     }
        // }
    }
    
});