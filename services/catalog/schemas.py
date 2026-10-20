from marshmallow import Schema, fields


class ProductIn(Schema):
    name = fields.String(required=True, description="Nome do produto")
    price = fields.Number(required=True, description="Preço")
    stock = fields.Integer(required=False, load_default=0, description="Estoque inicial")
    extendedWarrantyEligible = fields.Boolean(required=False, load_default=False, description="Elegível a garantia estendida")


class ProductUpdateIn(Schema):
    name = fields.String(required=False, description="Nome")
    price = fields.Number(required=False, description="Preço")
    stock = fields.Integer(required=False, description="Estoque")
    extendedWarrantyEligible = fields.Boolean(required=False, description="Elegível a garantia estendida")


class StockChangeIn(Schema):
    quantity = fields.Integer(required=False, load_default=1, description="Quantidade")