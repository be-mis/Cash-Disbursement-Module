from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

MEAL = (("BREAKFAST", "BREAKFAST"), ("LUNCH", "LUNCH"), ("DINNER", "DINNER"))

PAYMENT = (
    ("GCASH", "GCASH"),
    ("METROBANK", "METROBANK"),
    ("CASH", "CASH"),
)

BusinessUnit = (
    ("EPC", "EPC"),
    ("NBFI", "NBFI")
)


class MainTable(models.Model):
    fname = models.CharField(max_length=50)
    lname = models.CharField(max_length=50)
    businessUnit = models.CharField(max_length=100, choices=BusinessUnit)
    department = models.CharField(max_length=50)
    departureDate = models.DateTimeField(null=True, blank=True)
    returnDate = models.DateTimeField(null=True, blank=True)
    dateFiled = models.DateTimeField(auto_now=True) ################ Kelan na submit
    created = models.DateTimeField(auto_now_add=True) ############## Kelan inadd regardless of status (draft or saved/pending or submitted/approved/rejected)
    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)
    table_type = models.CharField(max_length=50)  # Added field
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.fname} {self.lname} - {self.purpose} ({self.table_type})"

    class Meta:
        ordering = ['-created']



class Transportation(models.Model):
    main_table = models.ForeignKey(MainTable, on_delete=models.CASCADE)  # Use MainTable
    date = models.DateTimeField()
    locFrom = models.CharField(max_length=100)
    locTo = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.date} - {self.locFrom} to {self.locTo}"

class Meal(models.Model):
    main_table = models.ForeignKey(MainTable, on_delete=models.CASCADE)  # Use MainTable
    date = models.DateTimeField()
    meal_type = models.CharField(max_length=200, choices=MEAL)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.date} - {self.meal_type}"

class Lodging(models.Model):
    main_table = models.ForeignKey(MainTable, on_delete=models.CASCADE)  # Use MainTable
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.check_in} - {self.check_out} ({self.description})"

class Purchase(models.Model):
    main_table = models.ForeignKey(MainTable, on_delete=models.CASCADE)  # Use MainTable
    date = models.DateTimeField()
    purchase_number = models.CharField(max_length=50)
    particulars = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Purchase #{self.purchase_number} - {self.particulars}"


####################--------------------Cash Reimbursement--------------------####################


class CashReimbursement(models.Model):
    fname = models.CharField(max_length=50)
    lname = models.CharField(max_length=50)
    businessUnit = models.CharField(max_length=100, choices=BusinessUnit)
    department = models.CharField(max_length=50)
    departureDate = models.DateTimeField(null=True, blank=True)
    returnDate = models.DateTimeField(null=True, blank=True)
    dateFiled = models.DateTimeField(auto_now=True) ################ Kelan na submit
    created = models.DateTimeField(auto_now_add=True) ############## Kelan inadd regardless of status (draft or saved/pending or submitted/approved/rejected)
    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)
    table_type = models.CharField(max_length=50)  # Added field
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.fname} {self.lname} - {self.purpose} ({self.table_type})"

    class Meta:
        ordering = ['-created']



class Transportation1(models.Model):
    reimbursement_table = models.ForeignKey(CashReimbursement, on_delete=models.CASCADE)  # Use MainTable
    date = models.DateTimeField()
    locFrom = models.CharField(max_length=100)
    locTo = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.date} - {self.locFrom} to {self.locTo}"

class Meal1(models.Model):
    reimbursement_table = models.ForeignKey(CashReimbursement, on_delete=models.CASCADE)  # Use MainTable
    date = models.DateTimeField()
    meal_type = models.CharField(max_length=200, choices=MEAL)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.date} - {self.meal_type}"

class Lodging1(models.Model):
    reimbursement_table = models.ForeignKey(CashReimbursement, on_delete=models.CASCADE)  # Use MainTable
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.check_in} - {self.check_out} ({self.description})"


