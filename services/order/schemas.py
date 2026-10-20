from marshmallow import Schema, fields


class CreateOrderIn(Schema):
    cartId = fields.String(required=True, description="ID do carrinho")


class OrderOut(Schema):
    orderId = fields.String(description="ID do pedido")
    status = fields.String(description="PENDING | PAID | REJECTED")
    total = fields.Number(description="Total do pedido")
    reason = fields.String(description="Motivo de rejeição (quando aplicável)")