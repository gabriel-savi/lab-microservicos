from marshmallow import Schema, fields


class CartItemIn(Schema):
    productId = fields.Integer(required=True, description="ID do produto no catálogo")
    quantity = fields.Integer(required=False, load_default=1, description="Quantidade")


class CartItemOut(Schema):
    productId = fields.Integer(description="ID do produto")
    name = fields.String(description="Nome do produto")
    price = fields.Number(description="Preço")
    quantity = fields.Integer(description="Quantidade")


class CartOut(Schema):
    cartId = fields.String(description="ID do carrinho")
    items = fields.List(fields.Nested(CartItemOut), description="Itens")
    total = fields.Number(description="Total")