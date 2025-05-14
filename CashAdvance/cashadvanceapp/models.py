from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

# Choices
MEAL = (("BREAKFAST", "BREAKFAST"), ("LUNCH", "LUNCH"), ("DINNER", "DINNER"))
PAYMENT = (("GCASH", "GCASH"), ("METROBANK", "METROBANK"), ("CASH", "CASH"))

# CashAdvance model
class CashAdvance(models.Model):
    #### Fetched from presto by sending session storage to django using Axios (Auto Filled when logged in)
    name = models.CharField(max_length=100)
    userEmail = models.CharField(max_length=255)
    userID = models.IntegerField()
    position = models.CharField(max_length=255)
    businessUnit = models.CharField(max_length=100)

    #### These records will come from user input (Manually filled by user)
    department = models.CharField(max_length=50)

    departureDate = models.DateField(null=True, blank=True)
    returnDate = models.DateField(null=True, blank=True)

    date_requested = models.DateField()
    date_needed = models.DateField()


    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)  #### Supports 'pending_liquidation'
    table_type = models.CharField(max_length=50)
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    # Relationships to sub-tables
    transportations = GenericRelation('Transportation', related_query_name='transportation')
    meals = GenericRelation('Meal', related_query_name='meal')
    lodgings = GenericRelation('Lodging', related_query_name='lodging')
    purchases = GenericRelation('Purchase', related_query_name='purchase')

    class Meta:
        ordering = ['-date_requested']

    def __str__(self):
        return f"{self.name} - {self.purpose} (CashAdvance)"


# CashLiquidation model
class CashLiquidation(models.Model):
    #### Link to the original CashAdvance
    cash_advance = models.ForeignKey(
        CashAdvance,
        on_delete=models.PROTECT,  #### Prevents deletion of CAR if CLR exists
        related_name='liquidations',
        null=True,  #### Allows CLR to be created independently if needed
        blank=True
    )

    #### Fetched from presto or copied from CashAdvance
    name = models.CharField(max_length=100)
    userEmail = models.CharField(max_length=255)
    userID = models.IntegerField()
    position = models.CharField(max_length=255)
    businessUnit = models.CharField(max_length=100)

    #### These records will come from user input or copied from CashAdvance
    department = models.CharField(max_length=50)
    departureDate = models.DateField(null=True, blank=True)
    returnDate = models.DateField(null=True, blank=True)

    date_requested = models.DateField()
    date_needed = models.DateField()

    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)
    table_type = models.CharField(max_length=50)
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    # Relationships to sub-tables
    transportations = GenericRelation('Transportation', related_query_name='transportation')
    meals = GenericRelation('Meal', related_query_name='meal')
    lodgings = GenericRelation('Lodging', related_query_name='lodging')
    purchases = GenericRelation('Purchase', related_query_name='purchase')

    class Meta:
        ordering = ['-date_requested']

    def __str__(self):
        return f"Liquidation for {self.name} - {self.status} (CAR ID: {self.cash_advance_id})"

# CashReimbursement model (Independent)
class CashReimbursement(models.Model):
    #### Fetched from presto by sending session storage to django using Axios (Auto Filled when logged in)
    name = models.CharField(max_length=100)
    userEmail = models.CharField(max_length=255)
    userID = models.IntegerField()
    position = models.CharField(max_length=255)
    businessUnit = models.CharField(max_length=100)

    #### These records will come from user input (Manually filled by user)
    department = models.CharField(max_length=50)
    departureDate = models.DateField(null=True, blank=True)
    returnDate = models.DateField(null=True, blank=True)

    date_requested = models.DateField()
    date_needed = models.DateField()


    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)
    table_type = models.CharField(max_length=50)
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    # Relationships to sub-tables
    transportations = GenericRelation('Transportation', related_query_name='transportation')
    meals = GenericRelation('Meal', related_query_name='meal')
    lodgings = GenericRelation('Lodging', related_query_name='lodging')
    purchases = GenericRelation('Purchase', related_query_name='purchase')

    class Meta:
        ordering = ['-date_requested']

    def __str__(self):
        return f"{self.name} - {self.purpose} (CashReimbursement)"

# Shared Transportation model
class Transportation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    date = models.DateField(null=True, blank=True)
    locFrom = models.CharField(max_length=100, null=True, blank=True)
    locTo = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)


    def __str__(self):
        return f"{self.date} - {self.locFrom} to {self.locTo}"

# Shared Meal model
class Meal(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    date = models.DateField(null=True, blank=True)
    meal_type = models.CharField(max_length=200, choices=MEAL, null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.meal_type}"

# Shared Lodging model
class Lodging(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    

    def __str__(self):
        return f"{self.check_in} - {self.check_out} ({self.description})"

# Shared Purchase model
class Purchase(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    purchase_number = models.IntegerField(null=True, blank=True)
    particulars = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)    

    def __str__(self):
        return f"Purchase #{self.purchase_number} - {self.particulars}"