@csrf_exempt
def cashadv(request):
    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    context = {
        "username":username,
        "user_id":user_id,
        "user_email":user_email,
        "session_id":session_id,
        "position":position,
        "company":company
    }

    if request.method == 'POST':
        try:
            action_type = request.POST.get('actionType')
            status = 'save' if action_type == 'save' else 'submitted'
            name = request.POST.get('name', '')
            user_email = request.POST.get('userEmail', '')
            user_id = request.POST.get('userID', '')
            position = request.POST.get('position', '')

            businessUnit = request.POST.get('bu', '').strip()
            dept = request.POST.get('dept', '').strip()
            purpose = request.POST.get('purpose', '').strip()
            payment_mode = request.POST.get('payment_method', '').strip().upper()
            account_number = request.POST.get('account_number', '').strip()
            departure_date = request.POST.get('departure_date_display')
            date_filed = datetime.today().strftime('%Y-%m-%d')
            return_date = request.POST.get('return_date_display')
            # departure_date = None if departure_date in ["", "null"] else departure_date
            # return_date = None if return_date in ["", "null"] else return_date

            # JSON data
            transportation_data = request.POST.get('transportationData', '[]')
            meal_data = request.POST.get('mealData', '[]')
            lodging_data = request.POST.get('lodgingData', '[]')

            try:
                transport_entries = json.loads(transportation_data) if transportation_data else []
                meal_entries = json.loads(meal_data) if meal_data else []
                lodging_entries = json.loads(lodging_data) if lodging_data else []
            except json.JSONDecodeError:
                return HttpResponse("Error: Invalid JSON format in request.", status=400)

            # Create main record
            print(f"my company is: {company}")
            main_table = CashAdvance.objects.create(
                name=name,
                userID=user_id,
                userEmail=user_email,
                position=position,
                businessUnit=businessUnit,
                department=dept,
                dateFiled=date_filed,
                departureDate=departure_date,
                returnDate=return_date,
                purpose=purpose,
                accountNumber=account_number,
                paymentMode=payment_mode,
                status=status,
                table_type="CashAdvance"
            )

            # Amount parsing function
            def parse_decimal(value):
                try:
                    return Decimal(value) if value else Decimal('0')
                except:
                    return Decimal('0')

            # Save Transportation
            for entry in transport_entries:
                Transportation.objects.create(
                    main_table=main_table,
                    date=entry.get('date'),
                    locFrom=entry.get('from', ''),
                    locTo=entry.get('to', ''),
                    description=entry.get('desc', ''),
                    amount=parse_decimal(entry.get('amount'))
                )

            # Save Meal
            for entry in meal_entries:
                Meal.objects.create(
                    main_table=main_table,
                    date=entry.get('date'),
                    meal_type=entry.get('mealType', '').upper(),
                    description=entry.get('desc', ''),
                    amount=parse_decimal(entry.get('amount'))
                )

            # Save Lodging
            for entry in lodging_entries:
                Lodging.objects.create(
                    main_table=main_table,
                    check_in=entry.get('checkIn'),
                    check_out=entry.get('checkOut'),
                    description=entry.get('desc', ''),
                    amount=parse_decimal(entry.get('amount'))
                )

            return HttpResponse(f"Successfully saved cash advance records with status '{status}'.")

        except Exception as e:
            return HttpResponse(f"Error: {str(e)}", status=400)

    return render(request, "cashadv.html", context)






#For Cash Advance
def get_main_data(request, main_id, table_type):
    """Returns data for the modal as JSON."""
    if table_type == 'CashAdvance':
        main_record = get_object_or_404(CashAdvance, id=main_id)
        content_type = ContentType.objects.get_for_model(CashAdvance)
    elif table_type == 'CashReimbursement':
        main_record = get_object_or_404(CashReimbursement, id=main_id)
        content_type = ContentType.objects.get_for_model(CashReimbursement)
    elif table_type == 'CashLiquidation':
        main_record = get_object_or_404(CashLiquidation, id=main_id)
        content_type = ContentType.objects.get_for_model(CashLiquidation)
    else:
        return JsonResponse({'error': 'Invalid Table Type'}, status=400)

    # Filter related objects using content_type and object_id
    transportation = Transportation.objects.filter(
        content_type=content_type,
        object_id=main_record.id
    ).values('date', 'locFrom', 'locTo', 'amount')
    
    meal = Meal.objects.filter(
        content_type=content_type,
        object_id=main_record.id
    ).values('date', 'meal_type', 'amount')
    
    lodging = Lodging.objects.filter(
        content_type=content_type,
        object_id=main_record.id
    ).values('check_in', 'check_out', 'amount', 'description')
    
    purchase = []
    if table_type == 'CashAdvance':
        purchase = Purchase.objects.filter(main_table=main_record).values(
            'date', 'purchase_number', 'particulars', 'amount'
        )
    elif table_type == 'CashLiquidation':
        purchase = main_record.purchases.all().values(
            'date', 'purchase_number', 'particulars', 'amount'
        )

    # Prepare response data
    data = {
        'main': {
            'name': main_record.name if hasattr(main_record, 'name') else str(main_record.main_table.name),
            'dateFiled': main_record.dateFiled.strftime('%Y-%m-%d') if hasattr(main_record, 'dateFiled') else None,
            'businessUnit': main_record.businessUnit if hasattr(main_record, 'businessUnit') else str(main_record.main_table.businessUnit),
            'department': main_record.department if hasattr(main_record, 'department') else str(main_record.main_table.department),
            'departureDate': main_record.departureDate.strftime('%Y-%m-%d') if hasattr(main_record, 'departureDate') and main_record.departureDate else None,
            'returnDate': main_record.returnDate.strftime('%Y-%m-%d') if hasattr(main_record, 'returnDate') and main_record.returnDate else None,
            'purpose': main_record.purpose if hasattr(main_record, 'purpose') else str(main_record.main_table.purpose),
            'status': main_record.status,
            'dateFiled': main_record.dateFiled,
            'paymentMode': main_record.paymentMode if hasattr(main_record, 'paymentMode') else str(main_record.main_table.paymentMode),
            'accountNumber': main_record.accountNumber if hasattr(main_record, 'accountNumber') else str(main_record.main_table.accountNumber),
            'rejection_reason': main_record.rejection_reason if hasattr(main_record, 'rejection_reason') else None,
            'table_type': main_record.table_type if hasattr(main_record, 'table_type') else 'CashLiquidation',
        },
        'transportation': list(transportation),
        'meal': list(meal),
        'lodging': list(lodging),
        'purchase': list(purchase),
    }
    return JsonResponse(data)

#For Purchase
def get_main_data1(request, main_id):
    """Returns data for the modal as JSON."""
    main_record = get_object_or_404(CashAdvance, id=main_id)

    purchase = Purchase.objects.filter(main_table=main_record).values(
        'date', 'purchase_number', 'particulars', 'amount'
    )
    data = {
        'main': {
            'name': main_record.name if hasattr(main_record, 'name') else str(main_record.main_table.name),
            'businessUnit': main_record.businessUnit,
            'department': main_record.department,
            'purpose': main_record.purpose,
            'dateFiled': main_record.dateFiled,
            'status': main_record.status,
            'paymentMode': main_record.paymentMode,
            'accountNumber': main_record.accountNumber,
            'rejection_reason': main_record.rejection_reason,
            'table_type': main_record.table_type,
        },
        'purchase': list(purchase),
    }
    return JsonResponse(data)





from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

# Choices
MEAL = (("BREAKFAST", "BREAKFAST"), ("LUNCH", "LUNCH"), ("DINNER", "DINNER"))
PAYMENT = (("GCASH", "GCASH"), ("METROBANK", "METROBANK"), ("CASH", "CASH"))

# Abstract base model for common fields
class MainTable(models.Model):
    #### Fetched from presto by sending session storage to django using Axios (Auto Filled when logged in)
    name = models.CharField(max_length=100, null=True, blank=True)
    userEmail = models.CharField(max_length=255, null=True, blank=True)
    userID = models.IntegerField(null=True, blank=True)
    position = models.CharField(max_length=255, null=True, blank=True)
    businessUnit = models.CharField(max_length=100)

    #### These records will come from user input (Manually filled by user)
    department = models.CharField(max_length=50)
    departureDate = models.DateTimeField(null=True, blank=True)
    returnDate = models.DateTimeField(null=True, blank=True)
    dateFiled = models.DateTimeField() #### Except for this one. We have a function that sets the dateFiled to the day it was submitted
    created = models.DateTimeField(auto_now_add=True)
    purpose = models.CharField(max_length=255)
    paymentMode = models.CharField(max_length=50, choices=PAYMENT)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20)
    table_type = models.CharField(max_length=50)
    rejection_reason = models.TextField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['-created']

# CashAdvance model
class CashAdvance(MainTable):
    liquidations = GenericRelation('CashLiquidation', related_query_name='cash_advance')
    transportations = GenericRelation('Transportation', related_query_name='transportation')
    meals = GenericRelation('Meal', related_query_name='meal')
    lodgings = GenericRelation('Lodging', related_query_name='lodging')

    def __str__(self):
        return f"{self.name} - {self.purpose} ({self.table_type})"

# CashReimbursement model
class CashReimbursement(MainTable):
    liquidations = GenericRelation('CashLiquidation', related_query_name='cash_reimbursement')
    transportations = GenericRelation('Transportation', related_query_name='transportation')
    meals = GenericRelation('Meal', related_query_name='meal')
    lodgings = GenericRelation('Lodging', related_query_name='lodging')

    def __str__(self):
        return f"{self.name} - {self.purpose} ({self.table_type})"

# Shared Transportation model
class Transportation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    date = models.DateTimeField()
    locFrom = models.CharField(max_length=100)
    locTo = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.locFrom} to {self.locTo}"

# Shared Meal model
class Meal(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    date = models.DateTimeField()
    meal_type = models.CharField(max_length=200, choices=MEAL)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.meal_type}"

# Shared Lodging model
class Lodging(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)

    def __str__(self):
        return f"{self.check_in} - {self.check_out} ({self.description})"

# Purchase model (tied to CashAdvance only)
class Purchase(models.Model):
    main_table = models.ForeignKey(CashAdvance, on_delete=models.CASCADE)
    date = models.DateTimeField()
    purchase_number = models.CharField(max_length=50)
    particulars = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    attachment = models.FileField(upload_to='receipts/', null=True, blank=True)

    def __str__(self):
        return f"Purchase #{self.purchase_number} - {self.particulars}"

# CashLiquidation model
class CashLiquidation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    user_object_id = models.PositiveIntegerField(null=True, blank=True)
    object_id = models.PositiveIntegerField()
    main_table = GenericForeignKey('content_type', 'object_id')

    name = models.CharField(max_length=255, null=True, blank=True)
    dateLiquidated = models.DateTimeField(null=True, blank=True) #### Except for this one. We have a function that sets the dateFiled to the day it was submitted
    department = models.CharField(max_length=255, null=True, blank=True)
    departureDate = models.DateTimeField(null=True, blank=True)
    returnDate = models.DateTimeField(null=True, blank=True)

    paymentMode = models.CharField(max_length=50, choices=PAYMENT, null=True, blank=True)
    accountNumber = models.CharField(max_length=20, null=True, blank=True)

    status = models.CharField(max_length=50)
    rejection_reason = models.TextField(null=True, blank=True)
    table_type = models.CharField(max_length=50, null=True, blank=True)
    dateFiled = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=255, null=True, blank=True)

    
    purchases = models.ManyToManyField(Purchase, blank=True)
    transportations = models.ManyToManyField(Transportation, blank=True)
    meals = models.ManyToManyField(Meal, blank=True)
    lodgings = models.ManyToManyField(Lodging, blank=True)

    def __str__(self):
        return f"Liquidation for {self.main_table.name} - {self.status}"
        




# @csrf_exempt
# def saveReim(request, table_type):
#     # Extract query parameters
#     username = request.GET.get("username")
#     user_id = request.GET.get("userId")
#     user_email = request.GET.get("useremail")
#     session_id = request.GET.get("sessionId")
#     position = request.GET.get("position")
#     company = request.GET.get("company")

#     context = {
#         "username": username,
#         "user_id": user_id,
#         "user_email": user_email,
#         "session_id": session_id,
#         "position": position,
#         "company": company
#     }

#     if request.method == 'POST':
#         try:
#             status = request.POST.get('actionType')

#             # Amount parsing function
#             def parse_decimal(value):
#                 try:
#                     return Decimal(value) if value else Decimal('0')
#                 except:
#                     return Decimal('0')

#             if table_type == 'CashReimbursement':
#                 # Extract and process form fields
#                 name = request.POST.get('name')
#                 bu = request.POST.get('bu')
#                 user_email = request.POST.get('userEmail')
#                 user_id = request.POST.get('userID')
#                 position = request.POST.get('position')
#                 dept = request.POST.get('dept')
#                 purpose = request.POST.get('purpose')
#                 payment_mode = request.POST.get('payment_method').upper()
#                 account_number = request.POST.get('account_number')

#                 departure_date = request.POST.get('departure_date_display')
#                 return_date = request.POST.get('return_date_display')

#                 date_requested = request.POST.get('date_requested')
#                 date_needed = request.POST.get('date_needed')

#                 logger.debug(f"CashReimbursement - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

#                 # Validate businessUnit
#                 if not bu:
#                     logger.error("businessUnit is empty for CashReimbursement")
#                     return HttpResponse("Error: Business Unit is required.", status=400)

#                 # Create CashReimbursement record
#                 main_table = CashReimbursement.objects.create(
#                     name=name,
#                     userEmail=user_email,
#                     userID=user_id,
#                     position=position,
#                     businessUnit=bu,
#                     department=dept,

#                     departureDate=departure_date,
#                     returnDate=return_date,

#                     date_needed=date_needed,
#                     date_requested=date_requested,

#                     date_filed=date_filed,
#                     created=timezone.now(),
#                     purpose=purpose,
#                     accountNumber=account_number,
#                     paymentMode=payment_mode,
#                     status=status,
#                     table_type="CashReimbursement"
#                 )

#                 # JSON data
#                 transportation_data = request.POST.get('transportationData', '[]')
#                 meal_data = request.POST.get('mealData', '[]')
#                 lodging_data = request.POST.get('lodgingData', '[]')

#                 try:
#                     transport_entries = json.loads(transportation_data) if transportation_data else []
#                     meal_entries = json.loads(meal_data) if meal_data else []
#                     lodging_entries = json.loads(lodging_data) if lodging_data else []
#                 except json.JSONDecodeError:
#                     logger.error("Invalid JSON format in request")
#                     return HttpResponse("Error: Invalid JSON format in request.", status=400)

#                 # Get ContentType for CashReimbursement
#                 content_type = ContentType.objects.get_for_model(CashReimbursement)

#                 # Save Transportation
#                 for entry in transport_entries:
#                     try:
#                         attachment = entry.get('attachment')
#                         if attachment:
#                             attachment = convert_to_webp(attachment)
#                         Transportation.objects.create(
#                             content_type=content_type,
#                             object_id=main_table.id,
#                             date=entry.get('date'),
#                             locFrom=entry.get('from', ''),
#                             locTo=entry.get('to', ''),
#                             description=entry.get('desc', ''),
#                             amount=parse_decimal(entry.get('amount')),
#                             attachment=attachment
#                         )
#                     except Exception as e:
#                         logger.error(f"Failed to create Transportation: {e}")
#                         return HttpResponse(f"Error creating Transportation: {str(e)}", status=400)

#                 # Save Meal
#                 for entry in meal_entries:
#                     try:
#                         attachment = entry.get('attachment')
#                         if attachment:
#                             attachment = convert_to_webp(attachment)
#                         Meal.objects.create(
#                             content_type=content_type,
#                             object_id=main_table.id,
#                             date=entry.get('date'),
#                             meal_type=entry.get('mealType', '').upper(),
#                             description=entry.get('desc', ''),
#                             amount=parse_decimal(entry.get('amount')),
#                             attachment=attachment
#                         )
#                     except Exception as e:
#                         logger.error(f"Failed to create Meal: {e}")
#                         return HttpResponse(f"Error creating Meal: {str(e)}", status=400)

#                 # Save Lodging
#                 for entry in lodging_entries:
#                     try:
#                         attachment = entry.get('attachment')
#                         if attachment:
#                             attachment = convert_to_webp(attachment)
#                         Lodging.objects.create(
#                             content_type=content_type,
#                             object_id=main_table.id,
#                             check_in=entry.get('checkIn'),
#                             check_out=entry.get('checkOut'),
#                             description=entry.get('desc', ''),
#                             amount=parse_decimal(entry.get('amount')),
#                             attachment=attachment
#                         )
#                     except Exception as e:
#                         logger.error(f"Failed to create Lodging: {e}")
#                         return HttpResponse(f"Error creating Lodging: {str(e)}", status=400)

#                 return HttpResponse(f"Successfully saved cash reimbursement records with status '{status}'.")

#             if table_type == 'Purchase':
#                 name = request.POST.get('pname')
#                 bu = request.POST.get('pbu')
#                 user_email = request.POST.get('puserEmail')
#                 user_id = request.POST.get('puserID')
#                 position = request.POST.get('pposition', position or '').strip()
#                 dept = request.POST.get('pdept', '').strip()
#                 purpose = request.POST.get('ppurpose', '').strip()
#                 payment_mode = request.POST.get('ppayment_method', '').strip().upper()
#                 account_number = request.POST.get('paccount_number', '').strip()
#                 date_needed = request.POST.get('pdate_needed') or None
#                 date_requested = request.POST.get('prequested_date') or None

#                 logger.debug(f"CashAdvance - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

#                 # Validate businessUnit
#                 if not bu:
#                     logger.error("businessUnit is empty for CashAdvance")
#                     return HttpResponse("Error: Business Unit is required.", status=400)

#                 # Create CashAdvance Purchase
#                 main_table = CashAdvance.objects.create(
#                     name=name,
#                     userEmail=user_email,
#                     userID=user_id,
#                     position=position,
#                     businessUnit=bu,
#                     date_needed=date_needed,
#                     date_requested=date_requested,
#                     department=dept,
#                     purpose=purpose,
#                     accountNumber=account_number,
#                     paymentMode=payment_mode,
#                     status=status,
#                     table_type="Purchase"
#                 )

#                 # JSON data
#                 purchase_data = request.POST.get('purchaseData', '[]')

#                 try:
#                     purchase_entries = json.loads(purchase_data) if purchase_data else []
#                 except json.JSONDecodeError:
#                     logger.error("Invalid JSON format in request")
#                     return HttpResponse("Error: Invalid JSON format in request.", status=400)

#                 # Get ContentType for CashAdvance
#                 cash_advance_content_type = ContentType.objects.get_for_model(CashAdvance)

#                 # Save Transportation
#                 for entry in purchase_entries:
#                     try:
#                         Purchase.objects.create(
#                             content_type=cash_advance_content_type,
#                             object_id=main_table.id,

#                             purchase_number=entry.get('purchase_number', ''),
#                             particulars=entry.get('particulars', ''),
#                             amount=parse_decimal(entry.get('amount')),
#                             attachment=None  # No attachment for CashAdvance
#                         )
#                     except Exception as e:
#                         logger.error(f"Failed to create Purchase: {e}")
#                         return HttpResponse(f"Error creating Purchase: {str(e)}", status=400)

#                 return HttpResponse(f"Successfully saved cash advance purchase records with status '{status}'.")

#         except Exception as e:
#             logger.error(f"Error creating record: {e}")
#             return HttpResponse(f"Error: {str(e)}", status=400)

#     return render(request, "cashreim.html", context)




@csrf_exempt
def cashreim(request):
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1

    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    today = datetime.today().strftime('%m/%d/%Y')

    db = "REIMBURSEMENT"

    # Check if 'itemlist' exists in session, otherwise set a default (e.g., empty list)
    itemlist = request.session.get('itemlist', [])

    context = {
        "username": username,
        "user_id": user_id,
        "user_email": user_email,
        "session_id": session_id,
        "position": position,
        "company": company,
        "today": today,
        "purchase_number": purchase_number,
        'itemlist': itemlist,
        'db': db
    }

    return render(request, "cashadv.html", context)



@csrf_exempt
def cashliq(request):
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1

    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    today = datetime.today().strftime('%m/%d/%Y')

    db = "LIQUIDATION"

    # Check if 'itemlist' exists in session, otherwise set a default (e.g., empty list)
    itemlist = request.session.get('itemlist', [])

    context = {
        "username": username,
        "user_id": user_id,
        "user_email": user_email,
        "session_id": session_id,
        "position": position,
        "company": company,
        "today": today,
        "purchase_number": purchase_number,
        'itemlist': itemlist,
        'db': db
    }

    return render(request, "cashadv.html", context)






@csrf_exempt
def savePurchase(request, table_type):
    # Extract query parameters
    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    context = {
        "username": username,
        "user_id": user_id,
        "user_email": user_email,
        "session_id": session_id,
        "position": position,
        "company": company
    }

    if request.method == 'POST':
        try:
            status = request.POST.get('actionType')

            # Amount parsing function
            def parse_decimal(value):
                try:
                    return Decimal(value) if value else Decimal('0')
                except:
                    return Decimal('0')

            if table_type == 'CashAdvance':
                # Form fields for CashAdvance
                name = request.POST.get('name')
                bu = request.POST.get('bu')
                user_email = request.POST.get('userEmail')
                user_id = request.POST.get('userID')
                position = request.POST.get('position')

                dept = request.POST.get('dept', '')
                purpose = request.POST.get('purpose', '')
                payment_mode = request.POST.get('payment_method', '').upper()
                account_number = request.POST.get('account_number', '')

                departure_date = request.POST.get('departure_date_display')
                return_date = request.POST.get('return_date_display')
                date_requested = request.POST.get('date_requested')
                date_needed = request.POST.get('date_needed')

                date_filed = request.POST.get('date_filed')

                logger.debug(f"CashAdvance - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for CashAdvance")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create CashAdvance
                main_table = CashAdvance.objects.create(
                    name=name,
                    userEmail=user_email,
                    userID=user_id,
                    position=position,
                    businessUnit=bu,
                    department=dept,

                    departureDate=departure_date,
                    returnDate=return_date,

                    date_needed=date_needed,
                    date_requested=date_requested,

                    date_filed=date_filed,

                    created=timezone.now(),
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="CashAdvance"
                )

                # JSON data
                transportation_data = request.POST.get('transportationData', '[]')
                meal_data = request.POST.get('mealData', '[]')
                lodging_data = request.POST.get('lodgingData', '[]')

                try:
                    transport_entries = json.loads(transportation_data) if transportation_data else []
                    meal_entries = json.loads(meal_data) if meal_data else []
                    lodging_entries = json.loads(lodging_data) if lodging_data else []
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format in request")
                    return HttpResponse("Error: Invalid JSON format in request.", status=400)

                # Get ContentType for CashAdvance
                cash_advance_content_type = ContentType.objects.get_for_model(CashAdvance)

                # Save Transportation
                for entry in transport_entries:
                    try:
                        Transportation.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from', ''),
                            locTo=entry.get('to', ''),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashAdvance
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Transportation: {e}")
                        return HttpResponse(f"Error creating Transportation: {str(e)}", status=400)

                # Save Meal
                for entry in meal_entries:
                    try:
                        Meal.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            meal_type=entry.get('mealType', '').upper(),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashAdvance
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Meal: {e}")
                        return HttpResponse(f"Error creating Meal: {str(e)}", status=400)

                # Save Lodging
                for entry in lodging_entries:
                    try:
                        Lodging.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            check_in=entry.get('checkIn'),
                            check_out=entry.get('checkOut'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashAdvance
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Lodging: {e}")
                        return HttpResponse(f"Error creating Lodging: {str(e)}", status=400)

                return HttpResponse(f"Successfully saved cash advance records with status '{status}'.")

            if table_type == 'Purchase':
                name = request.POST.get('pname')
                bu = request.POST.get('pbu')
                user_email = request.POST.get('puserEmail')
                user_id = request.POST.get('puserID')
                position = request.POST.get('pposition')


                dept = request.POST.get('pdept', '')
                purpose = request.POST.get('ppurpose', '')
                payment_mode = request.POST.get('ppayment_method', '').upper()
                account_number = request.POST.get('paccount_number', '')

                departure_date = request.POST.get('pdeparture_date_display')
                return_date = request.POST.get('preturn_date_display')
                date_filed = request.POST.get('date_filed')
                # date_requested = request.POST.get('date_requested')
                # date_needed = request.POST.get('date_needed')

                logger.debug(f"CashAdvancePurchase - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for CashAdvance")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create CashAdvance Purchase
                main_table = CashAdvance.objects.create(
                    name=name,
                    userEmail=user_email,
                    userID=user_id,
                    position=position,
                    businessUnit=bu,
                    department=dept,

                    departureDate=departure_date,
                    returnDate=return_date,

                    date_filed=date_filed,

                    # date_needed=date_needed,
                    # date_requested=date_requested,

                    created=timezone.now(),
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="Purchase"
                )

                # JSON data
                purchase_data = request.POST.get('purchaseData', '[]')

                try:
                    purchase_entries = json.loads(purchase_data) if purchase_data else []
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format in request")
                    return HttpResponse("Error: Invalid JSON format in request.", status=400)

                # Get ContentType for CashAdvance
                cash_advance_content_type = ContentType.objects.get_for_model(CashAdvance)

                # Save Transportation
                for entry in purchase_entries:
                    try:
                        Purchase.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,

                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashAdvance
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Purchase: {e}")
                        return HttpResponse(f"Error creating Purchase: {str(e)}", status=400)

                return HttpResponse(f"Successfully saved cash advance purchase records with status '{status}'.")

        except Exception as e:
            logger.error(f"Error creating CashAdvance: {e}")
            return HttpResponse(f"Error: {str(e)}", status=400)

    return render(request, "cashadv.html", context)





# def request_list(request):
#     # Fetch all records
#     cash_advances = CashAdvance.objects.all()
#     cash_reimbursements = CashReimbursement.objects.all()
#     cash_liquidations = CashLiquidation.objects.all()

#     # Combine them into a single queryset or list
#     # Since they inherit from MainTable or have similar fields, we can use a list
#     table_data = list(cash_advances) + list(cash_reimbursements) + list(cash_liquidations)

#     table_data.sort(key=lambda x: x.date_requested if hasattr(x, 'date_requested') else x.created, reverse=True)

#     return render(request, 'your_template.html', {'table': table_data})