from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import CashAdvance, CashLiquidation, Transportation, Meal, Lodging, Purchase

@receiver(post_save, sender=CashAdvance)
def create_liquidation(sender, instance, **kwargs):
    if instance.status != "pendingliquidation":
        return #if the pendingliquidation is not the current status, it will just return and not create a liquidation
    # Else, the liquidation request will be created and take the values from the cash advance request
    def process_liquidation():
        # Avoid duplicate
        if CashLiquidation.objects.filter(
            userID=instance.userID,
            purpose=instance.purpose
        ).exists():
            return

        # Create CashLiquidation
        liquidation = CashLiquidation.objects.create(
            cash_advance=instance,
            name=instance.name,
            userEmail=instance.userEmail,
            userID=instance.userID,
            position=instance.position,
            businessUnit=instance.businessUnit,
            department=instance.department,
            departureDate=instance.departureDate,
            returnDate=instance.returnDate,
            date_requested=instance.date_requested,
            date_needed=instance.date_needed,
            purpose=instance.purpose,
            paymentMode=instance.paymentMode,
            accountNumber=instance.accountNumber,
            status="forapproval",
            table_type="CashLiquidation",
            rejection_reason=None
        )

        # Use ContentType for GenericForeignKey
        content_type = ContentType.objects.get_for_model(CashLiquidation)

        # Transportations
        try:
            transportations = instance.transportations.all()
        except AttributeError:
            transportations = Transportation.objects.filter(
                content_type=ContentType.objects.get_for_model(CashAdvance),
                object_id=instance.id
            )
        for t in transportations:
            Transportation.objects.create(
                content_type=content_type,
                object_id=liquidation.id,
                date=t.date,
                locFrom=t.locFrom,
                locTo=t.locTo,
                description=t.description,
                amount=t.amount,
                attachment=t.attachment
            )

        # Meals
        try:
            meals = instance.meals.all()
        except AttributeError:
            meals = Meal.objects.filter(
                content_type=ContentType.objects.get_for_model(CashAdvance),
                object_id=instance.id
            )
        for m in meals:
            Meal.objects.create(
                content_type=content_type,
                object_id=liquidation.id,
                date=m.date,
                meal_type=m.meal_type,
                description=m.description,
                amount=m.amount,
                attachment=m.attachment
            )

        # Lodgings
        try:
            lodgings = instance.lodgings.all()
        except AttributeError:
            lodgings = Lodging.objects.filter(
                content_type=ContentType.objects.get_for_model(CashAdvance),
                object_id=instance.id
            )
        for l in lodgings:
            Lodging.objects.create(
                content_type=content_type,
                object_id=liquidation.id,
                check_in=l.check_in,
                check_out=l.check_out,
                description=l.description,
                amount=l.amount,
                attachment=l.attachment
            )

        # Purchases
        try:
            purchases = instance.purchases.all()
        except AttributeError:
            purchases = Purchase.objects.filter(
                content_type=ContentType.objects.get_for_model(CashAdvance),
                object_id=instance.id
            )
        for p in purchases:
            Purchase.objects.create(
                content_type=content_type,
                object_id=liquidation.id,
                date=p.date,
                purchase_number=p.purchase_number,
                particulars=p.particulars,
                amount=p.amount,
                attachment=p.attachment
            )

    # Ensure it runs after DB transaction is committed
    transaction.on_commit(process_liquidation)
