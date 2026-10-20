from marshmallow import Schema, fields


class PaymentIn(Schema):
    orderId = fields.String(required=True, description="ID do pedido")
    amount = fields.Integer(required=True, description="Valor em centavos/inteiro")


class PaymentOut(Schema):
    paymentId = fields.Integer(description="ID interno do pagamento")
    orderId = fields.String(description="ID do pedido")
    amount = fields.Integer(description="Valor")
    status = fields.String(description="APPROVED | REJECTED")