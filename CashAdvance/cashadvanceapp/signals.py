from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CashAdvance, CashLiquidation, Purchase, Transportation, Meal, Lodging
from django.contrib.contenttypes.models import ContentType

@receiver(post_save, sender=CashAdvance)
def create_liquidation(sender, instance, **kwargs):
    """Create a CashLiquidation record when CashAdvance status is set to 'pendingliquidation'."""
    if instance.status != "pendingliquidation": # Double check this!!!
        return

    # Check if a liquidation already exists to avoid duplicates
    # Since CashLiquidation is standalone, check for matching userID and purpose
    if CashLiquidation.objects.filter(
        userID=instance.userID,
        purpose=instance.purpose,
        dateFiled__date=timezone.now().date()
    ).exists():
        return

    # Create a new CashLiquidation record
    liquidation = CashLiquidation.objects.create(
        name=instance.name,
        userEmail=instance.userEmail,
        userID=instance.userID,
        position=instance.position,
        businessUnit=instance.businessUnit,
        department=instance.department,
        departureDate=instance.departureDate,
        returnDate=instance.returnDate,
        dateFiled=timezone.now(),
        created=timezone.now(),
        purpose=instance.purpose,
        paymentMode=instance.paymentMode,
        accountNumber=instance.accountNumber,
        status="draft",
        table_type="CashLiquidation",
        rejection_reason=None
    )

    # Copy related objects by creating new instances
    content_type = ContentType.objects.get_for_model(CashLiquidation)
    
    # Copy Transportations
    for transportation in instance.transportations.all():
        Transportation.objects.create(
            content_type=content_type,
            object_id=liquidation.id,
            date=transportation.date,
            locFrom=transportation.locFrom,
            locTo=transportation.locTo,
            description=transportation.description,
            amount=transportation.amount,
            attachment=transportation.attachment
        )

    # Copy Meals
    for meal in instance.meals.all():
        Meal.objects.create(
            content_type=content_type,
            object_id=liquidation.id,
            date=meal.date,
            meal_type=meal.meal_type,
            description=meal.description,
            amount=meal.amount,
            attachment=meal.attachment
        )

    # Copy Lodgings
    for lodging in instance.lodgings.all():
        Lodging.objects.create(
            content_type=content_type,
            object_id=liquidation.id,
            check_in=lodging.check_in,
            check_out=lodging.check_out,
            description=lodging.description,
            amount=lodging.amount,
            attachment=lodging.attachment
        )

    # Copy Purchases
    for purchase in instance.purchases.all():
        Purchase.objects.create(
            content_type=content_type,
            object_id=liquidation.id,
            date=purchase.date,
            purchase_number=purchase.purchase_number,
            particulars=purchase.particulars,
            amount=purchase.amount,
            attachment=purchase.attachment
        )





















# from django.db.models.signals import post_save
# from datetime import datetime
# from django.dispatch import receiver
# from django.contrib.contenttypes.models import ContentType
# from .models import CashAdvance, CashReimbursement, CashLiquidation, Purchase, Transportation, Meal, Lodging

# @receiver(post_save, sender=CashAdvance)
# @receiver(post_save, sender=CashReimbursement)
# def create_liquidation(sender, instance, **kwargs):
#     # Check if the instance is approved
#     if instance.status != "pendingliquidation":
#         return

#     # Determine the content type for the instance
#     content_type = ContentType.objects.get_for_model(instance)

#     # Check if a liquidation already exists to avoid duplicates
#     if CashLiquidation.objects.filter(
#         content_type=content_type,
#         object_id=instance.id
#     ).exists():
#         return

#     # Define common fields for CashLiquidation
#     liquidation_data = {
#         "name": instance.name,
#         "user_object_id": instance.userID,
#         "content_type": content_type,
#         "object_id": instance.id,
#         "dateLiquidated": datetime.today().strftime('%Y-%m-%d'),
#         "department": instance.department,
#         "departureDate": instance.departureDate,
#         "returnDate": instance.returnDate,
#         "paymentMode": instance.paymentMode,
#         "accountNumber": instance.accountNumber,
#         "dateFiled": instance.dateFiled,
#         "table_type": "CashLiquidation",
#         "purpose": instance.purpose,
#         "status": "pending",
#         "rejection_reason": None,
#     }

#     # Create a new CashLiquidation entry
#     liquidation = CashLiquidation.objects.create(**liquidation_data)

#     # Dynamically associate related objects
#     related_models = {
#         "purchases": Purchase,
#         "transportations": Transportation,
#         "meals": Meal,
#         "lodgings": Lodging,
#     }

#     for field_name, model in related_models.items():
#         # Check if the field exists in CashLiquidation
#         if hasattr(liquidation, field_name):
#             # Determine how to filter related objects
#             if isinstance(instance, CashAdvance) and field_name == "purchases":
#                 # Special case for Purchase linked via main_table
#                 related_objects = model.objects.filter(main_table=instance)
#             else:
#                 # General case for objects linked via content_type and object_id
#                 related_objects = model.objects.filter(
#                     content_type=content_type,
#                     object_id=instance.id
#                 )
#             # Set the related objects to the liquidation
#             getattr(liquidation, field_name).set(related_objects)

#     # Save the liquidation with all associations
#     liquidation.save()

