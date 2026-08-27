/** @odoo-module */


export const keyboard_shortcuts = [
    {
        id : 1,
        name : 'Order',
        columns : [
            [
                {
                    name : 'Payment',
                    keys : ['Shift','Y']
                },
                {
                    name : 'Order select up',
                    keys : ['Arrow Up']
                },
                {
                    name : 'Order select down',
                    keys : ['Arrow Down']
                }
            ],
            [
                {
                    name : 'Select Customer',
                    keys : ['Shift','C']
                },
                {
                    name : 'Refund',
                    keys : ['Shift','E']
                },
                {
                    name : 'Add Customer Note',
                    keys : ['Shift','N']
                }
            ],
            [
                {
                    name : 'Quantity',
                    keys : ['Shift','Q']
                },
                {
                    name : 'Discount',
                    keys : ['Shift','D']
                },
                {
                    name : 'Price',
                    keys : ['Shift','P']
                }
            ]
        ]
    },
    {
        id : 2,
        name : 'Product',
        columns : [
            [
                {
                    name : 'Select Product',
                    keys : ['ArrowLeft','Or','ArrowRight']
                },
                {
                    name : 'Add Product to Order Line',
                    keys : ['Enter']
                }
            ],
            [
                {
                    name : 'Toggle Category Selector',
                    keys : ['Ctrl','A']
                },
                {
                    name : 'Change Category',
                    keys : ['ArrowLeft','Or','ArrowRight']
                },
            ],
            [
                {
                    name : 'Search Bar',
                    keys : ['Shift','S']
                },
            ]
        ]
    },
    {
        id : 3,
        name : 'Payment',
        columns : [
            [
                {
                    name : 'Validate Order',
                    keys : ['Shift','Y']
                },
                {
                    name : 'Select Customer',
                    keys : ['Shift','C']
                },
            ],
            [
                {
                    name : 'Toggle Is To Invoice',
                    keys : ['Shift','I']
                },
                {
                    name : 'Shipping Date Picker',
                    keys : ['Shift','D']
                },
            ],
            [
                {
                    name : 'Open Cashbox',
                    keys : ['Shfit','B']
                },
                {
                    name : 'Add Tip',
                    keys : ['Shift','T']
                },
            ]
        ]
    },
    {
        id : 4,
        name : 'Navigation',
        columns : [
            [
                {
                    name : 'Close Session',
                    keys : ['Alt','X']
                },
                {
                    name : 'Close POS',
                    keys : ['Alt','C']
                },
            ],
            [
                {
                    name : 'Cash Move',
                    keys : ['Shift','M']
                },
                {
                    name : 'Show Orders',
                    keys : ['Shift','O']
                }
            ],
            [
                {
                    name : 'Push Pending Order',
                    keys : ['Alt','P']
                },
                {
                    name : 'Back',
                    keys : ['Escape']
                },
            ]
        ]
    }
]