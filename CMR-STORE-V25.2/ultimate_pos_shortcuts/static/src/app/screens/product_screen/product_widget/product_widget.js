/** @odoo-module **/

import { ProductsWidget as BaseProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";
import { useEffect, useState  } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";

export class ProductsWidget extends BaseProductsWidget {

    setup() {
        super.setup();
        this.state = useState({ productIndex : -1, selectedCategoryId : this.pos.selectedCategoryId, categorySelectorActive : false});
        this.env.bus.addEventListener('activate_category_selector', (ev) => {
            this.state.categorySelectorActive = ev.detail
        });

        const handleKeyPress = (e) => {
            if (e.shiftKey && ( e.key === 's' || e.key === 'S')) {
                const searchBarRef = this.searchBarRef;
                if (!searchBarRef) return;
                searchBarRef.focus();
                this.unfocusProduct();
                this.resetProductIndex();
            }
            else if(e.key === 'ArrowLeft' && this.productsToDisplay.length !== 0 && !this.state.categorySelectorActive) {
                this.setSelectedCategoryId();
                if (!this.productsToDisplayRef) return;
                if (this.state.productIndex > 0) {
                    this.unfocusProduct();
                    this.decreaseProductIndex();
                    this.focusProduct(this.productsToDisplayRef[this.state.productIndex])
                }
            } 
            else if(e.key === 'ArrowRight' && this.productsToDisplay.length !== 0 && !this.state.categorySelectorActive) {
                this.setSelectedCategoryId();
                if (!this.productsToDisplayRef) return;
                if (this.state.productIndex < this.productsToDisplayRef.length - 1) {
                    this.unfocusProduct();
                    this.increaseProductIndex();
                    this.focusProduct(this.productsToDisplayRef[this.state.productIndex])
                }
            }
            else if(e.key === 'Enter'){
                if(this.state.productIndex !== -1 && this.productsToDisplay.length > this.state.productIndex) {
                    this.pos.addProductToCurrentOrder(this.productsToDisplay[this.state.productIndex])
                    const searchBarRef = this.searchBarRef;
                    if (!searchBarRef) return;
                    searchBarRef.blur();
                } 
            }
        };

        useEffect(() => {
            document.body.addEventListener('keyup', handleKeyPress);

            return () => {
                document.body.removeEventListener('keyup', handleKeyPress);
            };
        });


    }
    get searchBarRef(){
        const el = this.productsWidgetRef.el;
        if (!el)return false;
        const i = el.getElementsByTagName('input');
        if (!i) return false;
        return i[0];
    }
    setSelectedCategoryId(){
        if(this.state.selectedCategoryId != this.pos.selectedCategoryId){
            this.state.selectedCategoryId = this.pos.selectedCategoryId;
            this.state.productIndex = -1;
        }
    }
    increaseProductIndex() {
        this.state.productIndex++;
    }
    decreaseProductIndex() {
        this.state.productIndex--;
    }
    resetProductIndex() {
        this.state.productIndex = -1;
    }
    focusProduct(product) {
        product.classList.add('product_active');
    }

    unfocusProduct() {
        const el = this.productsWidgetRef.el;
        if (!el) return;
        const product_active = el.getElementsByClassName('product_active')
        if(!(product_active.length > 0)) return; 
        for(let i=0;i < product_active.length;i++){
            product_active[i].classList.remove('product_active');
        }
    }

    get productsToDisplayRef() {
        const el = this.productsWidgetRef.el;
        if (!el) return null;
        return el.getElementsByClassName('product');
    }
}