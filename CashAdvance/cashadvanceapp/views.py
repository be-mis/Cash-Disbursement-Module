from django.shortcuts import render, redirect, get_object_or_404
from .models import CashAdvance, Transportation, Meal, Lodging, Purchase, CashReimbursement, CashLiquidation
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
import time, tempfile
from datetime import datetime
from django.db import DatabaseError
from django.db.models import Count
import pytesseract
from PIL import Image
from django.utils.timezone import localtime
from decimal import Decimal
from django.db.models import Q, F
from django.core.mail import send_mail
from pdf2image import convert_from_bytes, convert_from_path
import os, io, mimetypes, json, pprint, logging

# This will change depending on the location of your Tesseract-OCR installation (You can find the tesseract location inside 100.62 where CDM project - CashAdvance is deployed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR'
# Set up logging
logger = logging.getLogger(__name__)

# Collecting data from the dynamic tables
transportations = []
meals = []
lodgings = []

# Common status mapping
STATUS_MAPPING = {
    'draft': 'Draft',
    'forapproval': 'For_Approval',
    'forprocess': 'For_Process',
    'forrelease': 'For_Release',
    'pendingliquidation': 'Pending_Liquidation',
    'denied': 'Denied',
    'completed': 'Completed'
}


###   IMPORTANT!!!!
###   THE LOGIC FOR GA & APPROVER BUTTONS IS INSIDE THE OPENMODAL (cadashboard, crdashboard, and cldashboard) JS FUNCTION
###   IN THE HTML FILES
###   YOU CAN ADD THE GA (General Accounting) AND APPROVER NAMES THERE
###   The encryption of the account number is also there


GA = ['Shiela Prado', 'Gian Francisco'] #can use the user id or username once the account is created in presto

# Dictionary mapping approvers to their departments
APPROVER_DEPARTMENTS = {
    'Justine Anaya': 'NBFI MERCHANDISING',
    'Maria Teresa Magsino': 'EPC MERCHANDISING',
    'Czareen Yanson': 'NBFI SALES',
    'Renalen Enchano': 'EPC SALES',
    'Rowena Llarena': 'HR',
    'Raiza Marie Limpiada': 'MARKETING',
    'Maria Diana Cabrera': 'OPERATIONS',
    'Mirare Alforja': 'FINANCE',
    'Jonathan Emmanuel Francisco': 'MIS',
    'Roland Alavera': 'MIS',

}

## This is a mapping of the status to be used in the dashboard
STATUS_TRANSITIONS = {
    'CashAdvance': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed'],
    'PurchaseAdvance': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed'],
    'PurchaseReimbursement': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed'],
    'PurchaseLiquidation': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed'],
    'CashReimbursement': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed'],
    'CashLiquidation': ['forapproval', 'forprocess', 'forrelease', 'pendingliquidation', 'completed']
}


# Default status count dictionary
DEFAULT_STATUS_COUNTS = {
    'All': 0,
    'For_Approval': 0, 'For_Process': 0, 'For_Release': 0,
    'Denied': 0, 'Draft': 0, 'Completed': 0, 'Pending_Liquidation': 0
}



'''
Separate dashboard rendering for Cash Advance, Reimbursement and Liquidation
'''


# This function is used to get the user data from PRESTO through session

def get_request_user_data(request):
    source = request.POST if request.method == 'POST' else request.GET
    return {
        'username': source.get("username"),
        'user_id': source.get("userId"),
        'user_email': source.get("useremail"),
        'session_id': source.get("sessionId"),
        'position': source.get("position"),
        'company': source.get("company")
    }


# Helper function to calculate status counts. This function is reusable for all three dashboards
def calculate_status_counts(queryset):
    counts = DEFAULT_STATUS_COUNTS.copy()
    counts['All'] = queryset.count()
    for item in queryset.values('status').annotate(count=Count('status')):
        key = STATUS_MAPPING.get(item['status'], 'All')
        counts[key] += item['count']
    return counts


# Helper function to serialize records. This function is reusable for all three dashboards
def serialize_records(queryset):
    return [{
        'id': record.id,
        'date_needed': record.date_needed,
        'date_requested': record.date_requested,
        'departureDate': record.departureDate,
        'returnDate': record.returnDate,
        'purpose': record.purpose,
        'status': record.status,
        'payment': record.paymentMode,
        'name': record.name,
        'table_type': record.table_type,
    } for record in queryset]


## These three dashboards renders the same template format but with different databases
## We pass the corresponding context dictionary to the template
@csrf_exempt
def ca_dashboard(request):
    data = get_request_user_data(request)
    username = data.get('username')
    user_id = data.get('user_id')
    company = data.get('company')
    position = data.get('position')
    db = "ADVANCE"

    if not username or not user_id:
        print("Error: Missing username or user_id")
        return render(request, 'cadashboard.html', {'error': 'Missing username or user_id'})

    department = APPROVER_DEPARTMENTS.get(username)
    is_approver = department is not None
    is_ga = username in GA

    # Initialize querysets
    queryset = CashAdvance.objects.none()
    editable_queryset = CashAdvance.objects.none()

    if is_ga:
        # GA: View own requests and others' requests except 'draft' and 'forapproval'
        own_requests = CashAdvance.objects.filter(name=username).exclude(status='draft')
        others_requests = CashAdvance.objects.exclude(name=username).exclude(status__in=['draft', 'forapproval'])
        queryset = (own_requests | others_requests).distinct()
        # Editable: Own drafts and others' forprocess
        own_drafts = CashAdvance.objects.filter(name=username, status='draft')
        others_forprocess = CashAdvance.objects.exclude(name=username).filter(status='forprocess')
        editable_queryset = (own_drafts | others_forprocess).distinct()
    elif is_approver:
        # Approver: View own requests and department's forapproval requests
        own_requests = CashAdvance.objects.filter(name=username).exclude(status='draft')
        dept_requests = CashAdvance.objects.filter(department=department, status='forapproval')
        queryset = (own_requests | dept_requests).distinct()
    else:
        # Staff: View own requests only
        queryset = CashAdvance.objects.filter(name=username).exclude(status='draft')

    context = {
        'table': serialize_records(queryset),
        'editable': serialize_records(editable_queryset) if is_ga else [],
        'status_counts': calculate_status_counts(queryset),
        **data,
        'username': username,
        'db': db,
        'position': position,
        'is_ga': is_ga

    }

    return render(request, 'cadashboard.html', context)

@csrf_exempt
def cr_dashboard(request):
    data = get_request_user_data(request)
    username = data.get('username')
    user_id = data.get('user_id')
    company = data.get('company')
    db = 'REIMBURSEMENT'


    if not username or not user_id:
        print("Error: Missing username or user_id")
        return render(request, 'crdashboard.html', {'error': 'Missing username or user_id'})

    department = APPROVER_DEPARTMENTS.get(username)
    is_approver = department is not None
    is_ga = username in GA

    # Initialize queryset
    queryset = CashReimbursement.objects.none()

    if is_ga:
        own_requests = CashReimbursement.objects.filter(name=username).exclude(status='draft')
        others_requests = CashReimbursement.objects.exclude(name=username).exclude(status__in=['draft', 'forapproval'])
        queryset = (own_requests | others_requests).distinct()
    elif is_approver:
        own_requests = CashReimbursement.objects.filter(name=username).exclude(status='draft')
        dept_requests = CashReimbursement.objects.filter(department=department, status='forapproval')
        queryset = (own_requests | dept_requests).distinct()
    else:
        queryset = CashReimbursement.objects.filter(name=username).exclude(status='draft')

    context = {
        'table': serialize_records(queryset),
        'status_counts': calculate_status_counts(queryset),
        **data,
        'db': db,
        'is_ga': is_ga
    }

    return render(request, 'crdashboard.html', context)

@csrf_exempt
def cl_dashboard(request):
    data = get_request_user_data(request)
    username = data.get('username')
    user_id = data.get('user_id')
    company = data.get('company')
    db = 'LIQUIDATION'

    print(f"CL Dashboard params: username={username}, user_id={user_id}, company={company}")

    if not username or not user_id:
        print("Error: Missing username or user_id")
        return render(request, 'cldashboard.html', {'error': 'Missing username or user_id'})

    department = APPROVER_DEPARTMENTS.get(username)
    is_approver = department is not None
    is_ga = username in GA

    # Initialize querysets
    queryset = CashLiquidation.objects.none()
    editable_queryset = CashLiquidation.objects.none()

    if is_ga:
        own_requests = CashLiquidation.objects.filter(name=username).exclude(status='draft')
        others_requests = CashLiquidation.objects.exclude(name=username).exclude(status__in=['draft', 'forapproval'])
        queryset = (own_requests | others_requests).distinct()
        # Editable: Own drafts and others' forprocess
        own_drafts = CashLiquidation.objects.filter(name=username, status='draft')
        others_forprocess = CashLiquidation.objects.exclude(name=username).filter(status='forprocess')
        editable_queryset = (own_drafts | others_forprocess).distinct()
    elif is_approver:
        own_requests = CashLiquidation.objects.filter(name=username).exclude(status='draft')
        dept_requests = CashLiquidation.objects.filter(department=department, status='forapproval')
        queryset = (own_requests | dept_requests).distinct()
    else:
        queryset = CashLiquidation.objects.filter(name=username).exclude(status='draft')

    context = {
        'table': serialize_records(queryset),
        'editable': serialize_records(editable_queryset) if is_ga else [],
        'status_counts': calculate_status_counts(queryset),
        **data,
        'db': db,
        'is_ga': is_ga

    }

    return render(request, 'cldashboard.html', context)


'''
Dashboard rendering ends here
'''


##### Email notification Start #####
def send_test_email(request):
    ## we can access the user's email which we saved to our database and replace the recipient list
    ## 
    send_mail(
    subject='Test Email',
    message='This is a test.',
    from_email='jonathan.francisco@barbizonfashion.com',
    recipient_list=['diemrld12@gmail.com'],  # Replace with a valid email
    fail_silently=False,
    )
    subject = 'Test Email from Django'
    message = 'This is a test email sent from your Django app.'
    from_email = 'diemrld12@gmail.com'  # Same as EMAIL_HOST_USER
    recipient_list = ['newbarbizon360@gmail.com']  # Replace with a real email (userEmail from models)

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        return HttpResponse('Email sent successfully!')
    except Exception as e:
        return HttpResponse(f'Error sending email: {str(e)}')
##### Email notification End #####


## This function is used to search for records in the database
## It will be a reusable function for all three databases (cash advance, reimbursement and liquidation)
## Passing the db parameter will determine which database to use
@csrf_exempt
def search(request, db):
    if request.method != 'GET':
        logger.error(f"Invalid method: {request.method}")
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    search_word = request.GET.get('word', '').strip()

    if not username or not user_id:
        logger.error(f"Missing parameters: username={username}, user_id={user_id}")
        return JsonResponse({'error': 'Missing username or userId'}, status=400)

    try:
        user_id = int(user_id)
    except ValueError:
        logger.error(f"Invalid user_id: {user_id}")
        return JsonResponse({'error': 'Invalid userId'}, status=400)

    is_approver = username in APPROVER_DEPARTMENTS
    department = APPROVER_DEPARTMENTS.get(username, None)

    model_map = {
        'CashAdvance': CashAdvance,
        'CashReimbursement': CashReimbursement,
        'CashLiquidation': CashLiquidation
    }

    if db not in model_map:
        logger.error(f"Invalid db parameter: {db}")
        return JsonResponse({'error': f'Unknown database: {db}'}, status=400)

    model = model_map[db]

    try:
        # Base queryset based on user role
        if is_approver:
            queryset = model.objects.filter(department=department)
        else:
            queryset = model.objects.filter(name=username)

        # Apply search filter if provided
        if search_word:
            search_filters = (
                Q(name__icontains=search_word) |
                Q(purpose__icontains=search_word) |
                Q(table_type__icontains=search_word) |
                Q(status__icontains=search_word)
            )
            queryset = queryset.filter(search_filters)

        # Serialize the filtered results
        records = [{
            'id': record.id,
            'date_requested': record.date_requested.isoformat() if record.date_requested else None,
            'purpose': record.purpose,
            'table_type': record.table_type,
            'status': record.status,
            'name': record.name
        } for record in queryset]

        logger.info(f"Search completed: db={db}, word={search_word}, user_id={user_id}, records={len(records)}")
        return JsonResponse({'records': records})

    except Exception as e:
        logger.error(f"Unexpected error during query/serialization: {str(e)}")
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)


# This function retrieves the main data for a specific record based on its ID and table type.
# It will then be used to populat the viewing form for the approver and GA to see / edit / approve and reject data
@csrf_exempt
def get_main_data(request, main_id, table_type):
    try:
        # Mapping of table_type to model
        table_type_mapping = {
            'CashAdvance': (CashAdvance, 'CashAdvance'),
            'CashReimbursement': (CashReimbursement, 'CashReimbursement'),
            'CashLiquidation': (CashLiquidation, 'CashLiquidation'),
            'PurchaseAdvance': (CashAdvance, 'PurchaseAdvance'),
            'PurchaseReimbursement': (CashReimbursement, 'PurchaseReimbursement'),
            'PurchaseLiquidation': (CashLiquidation, 'PurchaseLiquidation'),
        }

        # Retrieve model and exact table_type
        model_class, expected_type = table_type_mapping.get(table_type, (None, None))
        if model_class is None:
            raise Http404(f"Unknown table_type: {table_type}")

        # Fetch the main record and content type
        main_record = get_object_or_404(model_class, id=main_id, table_type=expected_type)
        content_type = ContentType.objects.get_for_model(model_class)

        # Filter related objects
        transportation = Transportation.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values('date', 'locFrom', 'locTo', 'amount', 'attachment', 'description')

        meal = Meal.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values('date', 'meal_type', 'amount', 'attachment', 'description')

        lodging = Lodging.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values('check_in', 'check_out', 'amount', 'attachment', 'description')

        # Fetch purchase data without querying date_requested
        purchase = Purchase.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values(
            'purchase_number',
            'particulars',
            'attachment', 
            'amount'
        )

        # Convert purchase queryset to list and add requesteddate_date_requested from main_record
        purchase_list = list(purchase)
        for item in purchase_list:
            item['date'] = main_record.date_requested.strftime('%Y-%m-%d')

        # Prepare response data
        data = {
            'main': {
                'name': main_record.name,
                'businessUnit': main_record.businessUnit,
                'department': main_record.department,
                'purpose': main_record.purpose,
                'status': main_record.status,
                'date_requested': main_record.date_requested.strftime('%Y-%m-%d'),
                'paymentMode': main_record.paymentMode,
                'accountNumber': main_record.accountNumber,
                'rejection_reason': main_record.rejection_reason,
                'table_type': main_record.table_type or '',
            },
            'transportation': list(transportation),
            'meal': list(meal),
            'lodging': list(lodging),
            'purchase': purchase_list,  # Use modified purchase list
        }

        # Add travel-related fields only for non-Purchase table types
        if not table_type.startswith('Purchase'):
            data['main'].update({
                'departureDate': main_record.departureDate.strftime('%Y-%m-%d'),
                'returnDate': main_record.returnDate.strftime('%Y-%m-%d'),
                'date_requested': main_record.date_requested.strftime('%Y-%m-%d'),
                'date_needed': main_record.date_needed.strftime('%Y-%m-%d')
            })

        return JsonResponse(data)
    except (CashAdvance.DoesNotExist, CashReimbursement.DoesNotExist, CashLiquidation.DoesNotExist):
        logger.error(f"Record not found: id={main_id}, table_type={table_type}")
        return JsonResponse({'error': 'Record not found'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching record: id={main_id}, table_type={table_type}, error={str(e)}")
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)



## I separated the function for searching through drafts
## This ensures a more robust filtering and avoids conflict
## with the existing search function
@csrf_exempt
def draftsearch(request, db):
    if request.method != 'GET':
        logger.error(f"Invalid method: {request.method}")
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    username = request.GET.get("username")
    user_id = request.GET.get("userId")

    search_word = request.GET.get('word', '').strip()

    if not username or not user_id:
        logger.error(f"Missing parameters: username={username}, user_id={user_id}")
        return JsonResponse({'error': 'Missing username or userId'}, status=400)

    try:
        user_id = int(user_id)
    except ValueError:
        logger.error(f"Invalid user_id: {user_id}")
        return JsonResponse({'error': 'Invalid userId'}, status=400)

    model_map = {
        'CashAdvance': CashAdvance,
        'CashReimbursement': CashReimbursement,
        'CashLiquidation': CashLiquidation
    }

    if db not in model_map:
        logger.error(f"Invalid db parameter: {db}")
        return JsonResponse({'error': f'Unknown database: {db}'}, status=400)

    model = model_map[db]

    try:
        # Base queryset: only user's own records with status 'draft'
        queryset = model.objects.filter(name=username, status='draft')

        # Apply search filter if provided
        if search_word:
            search_filters = (
                Q(name__icontains=search_word) |
                Q(purpose__icontains=search_word) |
                Q(table_type__icontains=search_word)
            )
            queryset = queryset.filter(search_filters)

        # Serialize the filtered results
        records = [{
            'id': record.id,
            'date_requested': record.date_requested.isoformat() if record.date_requested else None,
            'purpose': record.purpose,
            'table_type': record.table_type,
            'status': record.status,
            'name': record.name
        } for record in queryset]

        logger.info(f"Search completed: db={db}, word={search_word}, user_id={user_id}, records={len(records)}")
        return JsonResponse({'records': records})

    except Exception as e:
        logger.error(f"Unexpected error during query/serialization: {str(e)}")
        return JsonResponse({'error': f'Internal server error: {str(e)}'}, status=500)




### These three functions renders the same template but with different database
## We pass a database identifiers to the template to determine which database to use
## Based on those identifiers, we will choose which url to use in saving the data
## Those saving functions are as follows below: saveAdvance, saveReimbursement, saveLiquidation

@csrf_exempt
def cashadv(request):
    db = "ADVANCE"
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1
    print(purchase_number)

    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")
    today = datetime.today().strftime('%m/%d/%Y')
    # Get user's draft cash advances
    draftlist = CashAdvance.objects.filter(name=username, status='draft')
    # Check if 'itemlist' exists in session
    itemlist = request.session.get('itemlist', [])

    context = {
        "username": username,
        "user_id": user_id,
        "user_email": user_email,
        "session_id": session_id,
        "position": position,
        "company": company,
        "today": today,
        "purchase_number": purchase_number, # renders the last entered purchase_number + 1
        "itemlist": itemlist,
        "db": db,
        "draftlist": draftlist,  # included draft entries here
    }

    return render(request, "cashadv.html", context)

@csrf_exempt
def cashreim(request):
    db = "REIMBURSEMENT"    
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1
    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")
    today = datetime.today().strftime('%m/%d/%Y')
    draftlist = CashReimbursement.objects.filter(name=username, status='draft')
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
        'db': db,
        'draftlist': draftlist
    }

    return render(request, "cashadv.html", context)

@csrf_exempt
def cashliq(request):
    db = "LIQUIDATION"
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1
    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")
    today = datetime.today().strftime('%m/%d/%Y')
    draftlist = CashLiquidation.objects.filter(name=username, status='draft')
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
        'db': db,
        'draftlist': draftlist
    }

    return render(request, "cashadv.html", context)


### These functions are responsible for saving the data to the database
## They are called when the user submits the form
@csrf_exempt
def saveAdvance(request, table_type):
    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    if request.method == 'POST':
        try:
            status = request.POST.get('actionType')
            if table_type == 'CashAdvance':
                # Form fields for CashAdvance
                name = request.POST.get('name')
                bu = request.POST.get('bu')
                user_email = request.POST.get('userEmail')
                user_id = request.POST.get('userID')
                position = request.POST.get('position')
                dept = request.POST.get('dept', '')
                purpose = request.POST.get('purpose', '')
                payment_mode = request.POST.get('payment_method')
                account_number = request.POST.get('account_number')
                departure_date = request.POST.get('departure_date_display')
                return_date = request.POST.get('return_date_display')
                date_requested = parse_date(request.POST.get('date_requested'))
                date_needed = request.POST.get('date_needed')

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
                for index, entry in enumerate(transport_entries):
                    try:
                        Transportation.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from', ''),
                            locTo=entry.get('to', ''),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount'))
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Transportation at index {index}: {e}")
                        continue

                # Save Meal
                for index, entry in enumerate(meal_entries):
                    try:
                        Meal.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            meal_type=entry.get('mealType'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount'))
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Meal at index {index}: {e}")
                        continue

                # Save Lodging
                for index, entry in enumerate(lodging_entries):
                    try:
                        Lodging.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            check_in=entry.get('checkIn'),
                            check_out=entry.get('checkOut'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount'))
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Lodging at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash reimbursement records with status '{status}'.")

            if table_type == 'PurchaseAdvance':
                name = request.POST.get('pname')
                bu = request.POST.get('pbu')
                user_email = request.POST.get('puserEmail')
                user_id = request.POST.get('puserID')
                position = request.POST.get('pposition')
                dept = request.POST.get('pdept')
                purpose = request.POST.get('ppurpose')
                payment_mode = request.POST.get('ppayment_method')
                account_number = request.POST.get('paccount_number')
                date_requested = parse_date(request.POST.get('pdate_requested'))
                date_needed = request.POST.get('pdate_needed')

                logger.debug(f"CashAdvancePurchase - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                if not bu:
                    logger.error("businessUnit is empty for CashAdvance")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                main_table = CashAdvance.objects.create(
                    name=name,
                    userEmail=user_email,
                    userID=user_id,
                    position=position,
                    businessUnit=bu,
                    department=dept,
                    date_needed=date_needed,
                    date_requested=date_requested,
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="PurchaseAdvance"
                )

                purchase_data = request.POST.get('purchaseData', '[]')
                try:
                    purchase_entries = json.loads(purchase_data) if purchase_data else []
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format in request")
                    return HttpResponse("Error: Invalid JSON format in request.", status=400)

                cash_advance_content_type = ContentType.objects.get_for_model(CashAdvance)

                for index, entry in enumerate(purchase_entries):
                    try:
                        if not isinstance(entry, dict):
                            logger.error(f"Invalid entry at index {index}: {entry}")
                            continue

                        file_key = f'purchase_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        purchase = Purchase.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                        if attachment:
                            extracted_data = extract_text_from_attachment(request, attachment=attachment)
                            extracted_text = extracted_data[0] if extracted_data else 'No text extracted'
                            purchase.extracted_data = extracted_text
                            purchase.save()
                            logger.debug(f"Extracted text for purchase {purchase.id}: {extracted_text}")
                    except Exception as e:
                        logger.error(f"Failed to create Purchase at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash advance purchase records with status '{status}'.")

        except Exception as e:
            logger.error(f"Error creating CashAdvance: {e}")
            return HttpResponse(f"Error: {str(e)}", status=400)

    # Fixed redirect
    from django.urls import reverse
    return redirect(f"{reverse('cashadvance-page')}?username={username}&userId={user_id}&useremail={user_email}&sessionId={session_id}&position={position}&company={company}")


@csrf_exempt
def saveReimbursement(request, table_type):
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

            if table_type == 'CashReimbursement':
                # Form fields for CashReimbursement
                name = request.POST.get('name')
                bu = request.POST.get('bu')
                user_email = request.POST.get('userEmail')
                user_id = request.POST.get('userID')
                position = request.POST.get('position')
                dept = request.POST.get('dept', '')
                purpose = request.POST.get('purpose', '')
                payment_mode = request.POST.get('payment_method')
                account_number = request.POST.get('account_number')
                departure_date = request.POST.get('departure_date_display')
                return_date = request.POST.get('return_date_display')
                date_requested = parse_date(request.POST.get('date_requested'))
                date_needed = request.POST.get('date_needed')

                logger.debug(f"CashReimbursement - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for CashReimbursement")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create CashReimbursement
                main_table = CashReimbursement.objects.create(
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
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="CashReimbursement"
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

                # Get ContentType for CashReimbursement
                cash_reimbursement_content_type = ContentType.objects.get_for_model(CashReimbursement)

                # Save Transportation
                for index, entry in enumerate(transport_entries):
                    try:
                        file_key = f'transportation_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Transportation.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from', ''),
                            locTo=entry.get('to', ''),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Transportation at index {index}: {e}")
                        continue

                # Save Meal
                for index, entry in enumerate(meal_entries):
                    try:
                        file_key = f'meal_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Meal.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            meal_type=entry.get('mealType'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Meal at index {index}: {e}")
                        continue

                # Save Lodging
                for index, entry in enumerate(lodging_entries):
                    try:
                        file_key = f'lodging_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Lodging.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            check_in=entry.get('checkIn'),
                            check_out=entry.get('checkOut'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Lodging at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash reimbursement records with status '{status}'.")

            if table_type == 'PurchaseReimbursement':
                name = request.POST.get('pname')
                bu = request.POST.get('pbu')
                user_email = request.POST.get('puserEmail')
                user_id = request.POST.get('puserID')
                position = request.POST.get('pposition')
                dept = request.POST.get('pdept', '')
                purpose = request.POST.get('ppurpose', '')
                payment_mode = request.POST.get('ppayment_method')
                account_number = request.POST.get('paccount_number')
                date_requested = parse_date(request.POST.get('pdate_requested'))
                date_needed = request.POST.get('pdate_needed')

                logger.debug(f"PurchaseReimbursement - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for PurchaseReimbursement")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create PurchaseReimbursement
                main_table = CashReimbursement.objects.create(
                    name=name,
                    userEmail=user_email,
                    userID=user_id,
                    position=position,
                    businessUnit=bu,
                    department=dept,
                    date_needed=date_needed,
                    date_requested=date_requested,
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="PurchaseReimbursement"
                )

                # JSON data
                purchase_data = request.POST.get('purchaseData', '[]')

                try:
                    purchase_entries = json.loads(purchase_data) if purchase_data else []
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format in request")
                    return HttpResponse("Error: Invalid JSON format in request.", status=400)

                # Get ContentType for CashReimbursement
                cash_reimbursement_content_type = ContentType.objects.get_for_model(CashReimbursement)

                # Save Purchase
                for index, entry in enumerate(purchase_entries):
                    try:
                        if not isinstance(entry, dict):
                            logger.error(f"Invalid entry at index {index}: {entry}")
                            continue

                        file_key = f'purchase_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        purchase = Purchase.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                        if attachment:
                            extracted_data = extract_text_from_attachment(request, attachment=attachment)
                            extracted_text = extracted_data[0] if extracted_data else 'No text extracted'
                            purchase.extracted_data = extracted_text
                            purchase.save()
                            logger.debug(f"Extracted text for purchase {purchase.id}: {extracted_text}")
                    except Exception as e:
                        logger.error(f"Failed to create Purchase at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash reimbursement purchase records with status '{status}'.")

        except Exception as e:
            logger.error(f"Error creating CashReimbursement: {e}")
            return HttpResponse(f"Error: {str(e)}", status=400)

    return render(request, "cashadv.html", context)



@csrf_exempt
def saveLiquidation(request, table_type):
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

            if table_type == 'CashLiquidation':
                # Form fields for CashLiquidation
                name = request.POST.get('name')
                bu = request.POST.get('bu')
                user_email = request.POST.get('userEmail')
                user_id = request.POST.get('userID')
                position = request.POST.get('position')
                dept = request.POST.get('dept')
                purpose = request.POST.get('purpose')
                payment_mode = request.POST.get('payment_method')
                account_number = request.POST.get('account_number')
                departure_date = request.POST.get('departure_date_display')
                return_date = request.POST.get('return_date_display')
                date_requested = parse_date(request.POST.get('date_requested'))
                date_needed = request.POST.get('date_needed')

                logger.debug(f"CashLiquidation - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for CashLiquidation")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create CashLiquidation
                main_table = CashLiquidation.objects.create(
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
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="CashLiquidation"
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

                # Get ContentType for CashLiquidation
                cash_liquidation_content_type = ContentType.objects.get_for_model(CashLiquidation)

                # Save Transportation
                for index, entry in enumerate(transport_entries):
                    try:
                        file_key = f'transportation_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Transportation.objects.create(
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from', ''),
                            locTo=entry.get('to', ''),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Transportation at index {index}: {e}")
                        continue

                # Save Meal
                for index, entry in enumerate(meal_entries):
                    try:
                        file_key = f'meal_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Meal.objects.create(
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            meal_type=entry.get('mealType'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Meal at index {index}: {e}")
                        continue

                # Save Lodging
                for index, entry in enumerate(lodging_entries):
                    try:
                        file_key = f'lodging_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        Lodging.objects.create(
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,
                            check_in=entry.get('checkIn'),
                            check_out=entry.get('checkOut'),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Lodging at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash liquidation records with status '{status}'.")

            if table_type == 'PurchaseLiquidation':
                name = request.POST.get('pname')
                bu = request.POST.get('pbu')
                user_email = request.POST.get('puserEmail')
                user_id = request.POST.get('puserID')
                position = request.POST.get('pposition')
                dept = request.POST.get('pdept')
                purpose = request.POST.get('ppurpose')
                payment_mode = request.POST.get('ppayment_method')
                account_number = request.POST.get('paccount_number')
                date_requested = parse_date(request.POST.get('pdate_requested'))
                date_needed = request.POST.get('pdate_needed')

                logger.debug(f"PurchaseLiquidation - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for PurchaseLiquidation")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create PurchaseLiquidation
                main_table = CashLiquidation.objects.create(
                    name=name,
                    userEmail=user_email,
                    userID=user_id,
                    position=position,
                    businessUnit=bu,
                    department=dept,
                    date_needed=date_needed,
                    date_requested=date_requested,
                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="PurchaseLiquidation"
                )

                # JSON data
                purchase_data = request.POST.get('purchaseData', '[]')

                try:
                    purchase_entries = json.loads(purchase_data) if purchase_data else []
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format in request")
                    return HttpResponse("Error: Invalid JSON format in request.", status=400)

                # Get ContentType for CashLiquidation
                cash_liquidation_content_type = ContentType.objects.get_for_model(CashLiquidation)

                # Save Purchase
                for index, entry in enumerate(purchase_entries):
                    try:
                        if not isinstance(entry, dict):
                            logger.error(f"Invalid entry at index {index}: {entry}")
                            continue

                        file_key = f'purchase_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        if attachment:
                            if attachment.size > 10 * 1024 * 1024:
                                logger.error(f"Attachment too large: {attachment.name}")
                                raise ValueError("File too large")
                            if attachment.content_type not in ['application/pdf', 'image/jpeg', 'image/png']:
                                logger.error(f"Unsupported file type: {attachment.content_type}")
                                raise ValueError("Unsupported file type")

                        purchase = Purchase.objects.create(
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,
                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                        if attachment:
                            extracted_data = extract_text_from_attachment(request, attachment=attachment)
                            extracted_text = extracted_data[0] if extracted_data else 'No text extracted'
                            purchase.extracted_data = extracted_text
                            purchase.save()
                            logger.debug(f"Extracted text for purchase {purchase.id}: {extracted_text}")
                    except Exception as e:
                        logger.error(f"Failed to create Purchase at index {index}: {e}")
                        continue

                return HttpResponse(f"Successfully saved cash liquidation purchase records with status '{status}'.")

        except Exception as e:
            logger.error(f"Error creating CashLiquidation: {e}")
            return HttpResponse(f"Error: {str(e)}", status=400)

    return render(request, "cashadv.html", context)





# This function deletes the draft (Only the requestor can delete their own draft)
@csrf_exempt
def delete_main_data(request, main_id, table_type):
    try:
        if request.method != 'DELETE':
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

        model_map = {
            'CashAdvance': CashAdvance,
            'CashReimbursement': CashReimbursement,
            'CashLiquidation': CashLiquidation,
            'PurchaseAdvance': CashAdvance,
            'PurchaseReimbursement': CashReimbursement,
            'PurchaseLiquidation': CashAdvance
        }

        dashboard_map = {
            'CashAdvance': 'cashadvance-page',
            'CashReimbursement': 'cashreimbursement-page',
            'CashLiquidation': 'cashliquidation-page',
            'PurchaseAdvance': 'cashadvance-page',
            'PurchaseReimbursement': 'cashreimbursement-page',
            'PurchaseLiquidation': 'cashliquidation-page'
        }

        if table_type not in model_map:
            return JsonResponse({'status': 'error', 'message': f'Invalid Table Type: {table_type}'}, status=400)

        model = model_map[table_type]
        main_data = get_object_or_404(model, id=main_id)
        main_data.delete()

        # Get query parameters
        username = request.GET.get("username", "")
        user_id = request.GET.get("userId", "")
        user_email = request.GET.get("useremail", "")
        session_id = request.GET.get("sessionId", "")
        position = request.GET.get("position", "")
        company = request.GET.get("company", "")

        # Determine dashboard based on table_type
        dashboard_view_name = dashboard_map.get(table_type, 'dashboard-page')
        dashboard_url = reverse(dashboard_view_name)

        query_params = {
            'username': username,
            'userId': user_id,
            'userEmail': user_email,
            'sessionId': session_id,
            'position': position,
            'company': company,
            '_t': str(int(time.time())),
        }
        query_string = '&'.join(f"{k}={v}" for k, v in query_params.items() if v)
        redirect_url = f"{dashboard_url}?{query_string}"

        print(f"Delete successful: id={main_id}, table_type={table_type}, redirect_url={redirect_url}")

        return JsonResponse({
            'status': 'success',
            'message': 'Data deleted',
            'redirect_url': redirect_url
        })

    except model.DoesNotExist:
        print(f"Error: Record not found: id={main_id}, table_type={table_type}")
        return JsonResponse({'status': 'error', 'message': 'Record not found'}, status=404)
    except DatabaseError as e:
        print(f"Database error deleting id={main_id}, table_type={table_type}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Database error: {str(e)}'}, status=500)
    except Exception as e:
        print(f"Unexpected error deleting id={main_id}, table_type={table_type}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Unexpected error: {str(e)}'}, status=500)



# Approve request function
# This function is used to approve requests for all table types
# This was made to be reusable
@csrf_exempt
def approveRequest(request, main_id, table_type, username):
    try:
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

        model_mapping = {
            'CashAdvance': CashAdvance,
            'PurchaseAdvance': CashAdvance,
            'PurchaseReimbursement': CashReimbursement,
            'PurchaseLiquidation': CashLiquidation,
            'CashReimbursement': CashReimbursement,
            'CashLiquidation': CashLiquidation
        }

        if table_type not in model_mapping:
            return JsonResponse({'status': 'error', 'message': 'Invalid Table Type'}, status=400)

        model = model_mapping[table_type]
        
        # Use transaction and lock the record
        with transaction.atomic():
            main_record = get_object_or_404(model.objects.select_for_update(), id=main_id)

            # Prevent self-approval
            if hasattr(main_record, 'requester_username') and main_record.requester_username == username:
                return JsonResponse({'status': 'error', 'message': 'Cannot approve your own request'}, status=403)

            valid_statuses = STATUS_TRANSITIONS.get(table_type, [])
            if main_record.status not in valid_statuses:
                return JsonResponse({'status': 'error', 'message': 'Invalid current status'}, status=400)

            current_status_index = valid_statuses.index(main_record.status)
            if current_status_index + 1 >= len(valid_statuses):
                return JsonResponse({'status': 'error', 'message': 'No further status transitions available'}, status=400)

            next_status = valid_statuses[current_status_index + 1]

            if username in GA:
                if next_status not in ['forrelease', 'pendingliquidation', 'completed']:
                    return JsonResponse({'status': 'error', 'message': 'GA user not authorized for this transition'}, status=403)
            elif username in APPROVER_DEPARTMENTS:
                if next_status != 'forprocess':
                    return JsonResponse({'status': 'error', 'message': 'Department approver not authorized for this transition'}, status=403)
            else:
                return JsonResponse({'status': 'error', 'message': 'User not authorized to approve'}, status=403)

            main_record.status = next_status
            main_record.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Request approved successfully. New status: {next_status}'
        }, status=200)

    except (CashAdvance.DoesNotExist, CashReimbursement.DoesNotExist, CashLiquidation.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



# Reject request function
# This function is used to reject requests for all table types
# This was made to be reusable
@csrf_exempt
def rejectRequest(request, main_id, table_type, username):
    try:
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

        model_mapping = {
            'CashAdvance': CashAdvance,
            'PurchaseAdvance': CashAdvance,
            'PurchaseReimbursement': CashReimbursement,
            'PurchaseLiquidation': CashLiquidation,
            'CashReimbursement': CashReimbursement,
            'CashLiquidation': CashLiquidation
        }

        if table_type not in model_mapping:
            return JsonResponse({'status': 'error', 'message': 'Invalid Table Type'}, status=400)

        model = model_mapping[table_type]

        with transaction.atomic():
            main_record = get_object_or_404(model.objects.select_for_update(), id=main_id)

            # Prevent self-rejection
            if hasattr(main_record, 'requester_username') and main_record.requester_username == username:
                return JsonResponse({'status': 'error', 'message': 'Cannot reject your own request'}, status=403)

            valid_statuses = STATUS_TRANSITIONS.get(table_type, [])
            if main_record.status not in valid_statuses:
                return JsonResponse({'status': 'error', 'message': 'Invalid current status'}, status=400)

            # You can keep or adjust user authorization if needed here...

            # Set status directly to 'denied' (no next status)
            main_record.status = 'denied'

            try:
                data = json.loads(request.body)
                reason = data.get('rejectionReason', '')
            except json.JSONDecodeError:
                reason = ''

            main_record.rejection_reason = reason
            main_record.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Request rejected successfully',
            'new_status': 'denied'  # like approveRequest returns next_status
        }, status=200)

    except (CashAdvance.DoesNotExist, CashReimbursement.DoesNotExist, CashLiquidation.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




# Helper function to parse date strings into accepted formats
def parse_date(date_str):
    try:
        # Try MM/DD/YYYY first
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        try:
            # Fallback: already in YYYY-MM-DD
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


# Amount parsing function
def parse_decimal(value):
    try:
        return Decimal(value) if value else Decimal('0')
    except:
        return Decimal('0')


# cash_reimbursement = CashReimbursement.objects.get(id=2)
# liquidation = cash_reimbursement.liquidation  # This will return the related CashLiquidation


# After the if request.method == 'GET' block, you can create a POST request handler
# This part renders the data into our update template for updating the drafts
# We do have a separate function for updating the pending requests (Approver and GA ONLY can update)

@csrf_exempt
def updateRecord(request, id, table_type):
    data = get_request_user_data(request)
    username = data.get('username')
    user_email = data.get('user_email')
    user_id = data.get('user_id')
    session_id = data.get('session_id')
    company = data.get('company')
    position = data.get('position')
    mytable = table_type

    # Determine db type
    if mytable in ['CashAdvance', 'PurchaseAdvance']:
        db = 'ADVANCE'
    elif mytable in ['CashReimbursement', 'PurchaseReimbursement']:
        db = 'REIMBURSEMENT'
    elif mytable in ['CashLiquidation', 'PurchaseLiquidation']:
        db = 'LIQUIDATION'
    else:
        logger.error(f"Invalid table_type: {mytable}")
        return HttpResponse('No Table')

    model_map = {
        'CashAdvance': CashAdvance,
        'CashReimbursement': CashReimbursement,
        'CashLiquidation': CashLiquidation,
        'PurchaseAdvance': CashAdvance,
        'PurchaseReimbursement': CashReimbursement,
        'PurchaseLiquidation': CashLiquidation,
    }

    if mytable not in model_map:
        logger.error(f"Invalid table_type: {mytable}")
        return HttpResponse('No Table')

    ModelClass = model_map[mytable]
    main_record = get_object_or_404(ModelClass, id=id, table_type=mytable)
    content_type = ContentType.objects.get_for_model(ModelClass)

    if request.method == 'GET':
        # Fetch related objects
        transportation = Transportation.objects.filter(content_type=content_type, object_id=main_record.id)
        meal = Meal.objects.filter(content_type=content_type, object_id=main_record.id)
        lodging = Lodging.objects.filter(content_type=content_type, object_id=main_record.id)
        purchase = Purchase.objects.filter(content_type=content_type, object_id=main_record.id)

        # Convert querysets to lists of dictionaries
        transportation_list = [
            {
                'id': item.id,
                'date': item.date.strftime('%Y-%m-%d') if item.date else '',
                'from': item.locFrom,
                'to': item.locTo,
                'desc': item.description,
                'amount': str(item.amount),
                'attachment': item.attachment.url if item.attachment else ''
            } for item in transportation
        ]
        meal_list = [
            {
                'id': item.id,
                'date': item.date.strftime('%Y-%m-%d') if item.date else '',
                'mealType': item.meal_type,
                'desc': item.description,
                'amount': str(item.amount),
                'attachment': item.attachment.url if item.attachment else ''
            } for item in meal
        ]
        lodging_list = [
            {
                'id': item.id,
                'checkIn': item.check_in.strftime('%Y-%m-%d') if item.check_in else '',
                'checkOut': item.check_out.strftime('%Y-%m-%d') if item.check_out else '',
                'desc': item.description,
                'amount': str(item.amount),
                'attachment': item.attachment.url if item.attachment else ''
            } for item in lodging
        ]
        purchase_list = [
            {
                'id': item.id,
                'purchase_number': item.purchase_number,
                'particulars': item.particulars,
                'amount': str(item.amount),
                'attachment': item.attachment.url if item.attachment else ''
            } for item in purchase
        ]

        # Calculate totals in the backend
        transport_total = sum(float(item['amount']) for item in transportation_list if item['amount'])
        meal_total = sum(float(item['amount']) for item in meal_list if item['amount'])
        lodging_total = sum(float(item['amount']) for item in lodging_list if item['amount'])
        purchase_total = sum(float(item['amount']) for item in purchase_list if item['amount'])
        grand_total = transport_total + meal_total + lodging_total + purchase_total

        today = datetime.today().strftime('%Y-%m-%d')
        # Prepare data for template
        data = {
            'main': {
                'id': main_record.id,
                'username': main_record.name,
                'company': main_record.businessUnit,
                'department': main_record.department,
                'user_email': main_record.userEmail,
                'user_id': main_record.userID,
                'position': main_record.position,
                'businessUnit': main_record.businessUnit,
                'department': main_record.department,
                'departureDate': main_record.departureDate.strftime('%Y-%m-%d') if main_record.departureDate else '',
                'returnDate': main_record.returnDate.strftime('%Y-%m-%d') if main_record.returnDate else '',
                'date_requested': main_record.date_requested.strftime('%Y-%m-%d') if main_record.date_requested else '',
                'date_needed': main_record.date_needed.strftime('%Y-%m-%d') if main_record.date_needed else '',
                'purpose': main_record.purpose,
                'status': main_record.status,
                'paymentMode': main_record.paymentMode,
                'accountNumber': main_record.accountNumber,
                'rejection_reason': main_record.rejection_reason,
                'table_type': mytable,
            },
            'transportation_list': transportation_list,
            'meal_list': meal_list,
            'lodging_list': lodging_list,
            'purchase_list': purchase_list,
            'transport_total': transport_total,
            'meal_total': meal_total,
            'lodging_total': lodging_total,
            'purchase_total': purchase_total,
            'grand_total': grand_total,
            'today': today,
            'db': db
        }

        return render(request, 'update.html', data)

    elif request.method == 'POST':
        try:
            # Update main record
            main_record.name = request.POST.get('name')
            main_record.businessUnit = request.POST.get('bu')
            main_record.department = request.POST.get('dept')
            main_record.purpose = request.POST.get('purpose')
            main_record.date_needed = request.POST.get('date_needed')
            main_record.paymentMode = request.POST.get('payment_method')
            main_record.accountNumber = request.POST.get('account_number')
            main_record.status = 'forapproval'
            
            if mytable in ['CashAdvance', 'CashReimbursement', 'CashLiquidation']:
                main_record.departureDate = request.POST.get('departure_date_display')
                main_record.returnDate = request.POST.get('return_date_display')

                
            # Validate required fields (example)
            if not main_record.purpose:
                data['error'] = 'Purpose is required.'
                return render(request, 'update.html', data)
            main_record.save()

            # Handle related objects
            if mytable in ['CashAdvance', 'CashReimbursement', 'CashLiquidation']:
                # Transportation
                existing_ids = set(request.POST.getlist('transport_id[]'))
                current_ids = set(str(item.id) for item in Transportation.objects.filter(content_type=content_type, object_id=main_record.id))
                ids_to_delete = current_ids - existing_ids
                Transportation.objects.filter(id__in=ids_to_delete, content_type=content_type, object_id=main_record.id).delete()

                for i, transport_id in enumerate(request.POST.getlist('transport_id[]')):
                    date = request.POST.getlist('transport_date[]')[i]
                    loc_from = request.POST.getlist('transport_from[]')[i]
                    loc_to = request.POST.getlist('transport_to[]')[i]
                    desc = request.POST.getlist('transport_desc[]')[i]
                    amount = request.POST.getlist('transport_amount[]')[i]
                    attachment = request.FILES.getlist('transport_attachment[]')[i] if i < len(request.FILES.getlist('transport_attachment[]')) else None

                    if transport_id:  # Update existing
                        transport = Transportation.objects.get(id=transport_id, content_type=content_type, object_id=main_record.id)
                        transport.date = date or None
                        transport.locFrom = loc_from
                        transport.locTo = loc_to
                        transport.description = desc
                        transport.amount = float(amount) if amount else 0
                        if attachment:
                            transport.attachment = attachment
                        transport.save()
                    else:  # Create new
                        if date or loc_from or loc_to or desc or amount:
                            Transportation.objects.create(
                                content_type=content_type,
                                object_id=main_record.id,
                                date=date or None,
                                locFrom=loc_from,
                                locTo=loc_to,
                                description=desc,
                                amount=float(amount) if amount else 0,
                                attachment=attachment
                            )

                # Meal
                existing_ids = set(request.POST.getlist('meal_id[]'))
                current_ids = set(str(item.id) for item in Meal.objects.filter(content_type=content_type, object_id=main_record.id))
                ids_to_delete = current_ids - existing_ids
                Meal.objects.filter(id__in=ids_to_delete, content_type=content_type, object_id=main_record.id).delete()

                for i, meal_id in enumerate(request.POST.getlist('meal_id[]')):
                    date = request.POST.getlist('meal_date[]')[i]
                    meal_type = request.POST.getlist('meal_type[]')[i]
                    desc = request.POST.getlist('meal_desc[]')[i]
                    amount = request.POST.getlist('meal_amount[]')[i]
                    attachment = request.FILES.getlist('meal_attachment[]')[i] if i < len(request.FILES.getlist('meal_attachment[]')) else None

                    if meal_id:  # Update existing
                        meal = Meal.objects.get(id=meal_id, content_type=content_type, object_id=main_record.id)
                        meal.date = date or None
                        meal.meal_type = meal_type
                        meal.description = desc
                        meal.amount = float(amount) if amount else 0
                        if attachment:
                            meal.attachment = attachment
                        meal.save()
                    else:  # Create new
                        if date or meal_type or desc or amount:
                            Meal.objects.create(
                                content_type=content_type,
                                object_id=main_record.id,
                                date=date or None,
                                meal_type=meal_type,
                                description=desc,
                                amount=float(amount) if amount else 0,
                                attachment=attachment
                            )

            # Lodging
            existing_ids = set(request.POST.getlist('lodging_id[]'))
            current_ids = set(str(item.id) for item in Lodging.objects.filter(content_type=content_type, object_id=main_record.id))
            ids_to_delete = current_ids - existing_ids
            Lodging.objects.filter(id__in=ids_to_delete, content_type=content_type, object_id=main_record.id).delete()

            for i, lodging_id in enumerate(request.POST.getlist('lodging_id[]')):
                check_in = request.POST.getlist('lodging_checkin[]')[i]
                check_out = request.POST.getlist('lodging_checkout[]')[i]
                desc = request.POST.getlist('lodging_desc[]')[i]
                amount = request.POST.getlist('lodging_amount[]')[i]
                attachment = request.FILES.getlist('lodging_attachment[]')[i] if i < len(request.FILES.getlist('lodging_attachment[]')) else None

                if lodging_id:
                    lodging = Lodging.objects.get(id=lodging_id, content_type=content_type, object_id=main_record.id)
                    lodging.check_in = check_in or None
                    lodging.check_out = check_out or None
                    lodging.description = desc
                    lodging.amount = float(amount) if amount else 0
                    if attachment:
                        lodging.attachment = attachment
                    lodging.save()
                else:
                    if check_in or check_out or desc or amount:
                        Lodging.objects.create(
                            content_type=content_type,
                            object_id=main_record.id,
                            check_in=check_in or None,
                            check_out=check_out or None,
                            description=desc,
                            amount=float(amount) if amount else 0,
                            attachment=attachment
                        )

            # Purchase
            existing_ids = set(request.POST.getlist('purchase_id[]'))
            current_ids = set(str(item.id) for item in Purchase.objects.filter(content_type=content_type, object_id=main_record.id))
            ids_to_delete = current_ids - existing_ids
            Purchase.objects.filter(id__in=ids_to_delete, content_type=content_type, object_id=main_record.id).delete()

            for i, purchase_id in enumerate(request.POST.getlist('purchase_id[]')):
                purchase_number = request.POST.getlist('purchase_number[]')[i]
                particulars = request.POST.getlist('purchase_particulars[]')[i]
                amount = request.POST.getlist('purchase_amount[]')[i]
                attachment = request.FILES.getlist('purchase_attachment[]')[i] if i < len(request.FILES.getlist('purchase_attachment[]')) else None

                if purchase_id:
                    purchase = Purchase.objects.get(id=purchase_id, content_type=content_type, object_id=main_record.id)
                    purchase.purchase_number = purchase_number
                    purchase.particulars = particulars
                    purchase.amount = float(amount) if amount else 0
                    if attachment:
                        purchase.attachment = attachment
                    purchase.save()
                else:
                    if purchase_number or particulars or amount:
                        Purchase.objects.create(
                            content_type=content_type,
                            object_id=main_record.id,
                            purchase_number=purchase_number,
                            particulars=particulars,
                            amount=float(amount) if amount else 0,
                            attachment=attachment
                        )
            # FIX THIS PART. YOU CAN ADD A VALIDATOR FOR THE REVERSE
            # EX 
            # db = table_type
            # if db = 'CashAdvance':
            #   url = 'cashadvance-page'
            # elif db = 'CashReimbursement':
            #   url = 'cashreimbursement-page'
            # elif db = 'CashLiquidation':
            #   url = 'cashliquidation-page'
            # else:
            #   return HttpResponse('Error: Table Type not defined)
            # return redirect(f"{reverse(url)}?username={username}&userId={user_id}&useremail={user_email}&sessionId={session_id}&position={position}&company={company}")
            #
            #
            # This way, we can dynamically redirect the page to a specific form depending on which draft they submitted
            return redirect(f"{reverse('cashadvance-page')}?username={username}&userId={user_id}&useremail={user_email}&sessionId={session_id}&position={position}&company={company}")
        except Exception as e:
            import traceback
            error_message = f"Error updating record: {str(e)}"
            traceback_details = traceback.format_exc()

            logger.error(error_message)
            logger.error(traceback_details)

            print(error_message)
            print(traceback_details)

            return HttpResponse("Failed to update record.")


#Helper function to save text
@csrf_exempt
def save_text(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', 'No text provided')
            logger.debug(f"Received text: {text}")
            # Store text or process as needed
            return JsonResponse({'status': 'success', 'received_text': text})
        except json.JSONDecodeError:
            logger.error("Invalid JSON format")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    logger.error("Only POST requests allowed")
    return JsonResponse({'status': 'error', 'message': 'Only POST requests allowed'}, status=405)



#Helper function to process text
@csrf_exempt
def sampleextract(request):
    """
    View to render the client-side OCR template for manual file uploads.
    """
    if request.method == 'POST':
        attachment = request.FILES.get('fileInput')  # Matches <input id="fileInput">
        if not attachment:
            logger.error("No file uploaded")
            return HttpResponse("Error: No file uploaded", status=400)
        # Render template with attachment info (optional)
        return render(request, 'sampleextract.html', {'attachment_name': attachment.name})
    
    # For GET requests, render the template
    return render(request, 'sampleextract.html', {})



# Helper function to extract text from an attachment
@csrf_exempt
def extract_text_from_attachment(request, attachment=None):
    """
    Extract text from an attachment using pytesseract.
    """
    logger = logging.getLogger('tesseract')
    extracted_data = []

    if attachment:
        logger.debug(f"Attachment received: {attachment.name}, type: {attachment.content_type}")
        try:
            # Ensure custom temp directory exists
            temp_dir = "C:\\TempOCR"
            os.makedirs(temp_dir, exist_ok=True)

            # Save original uploaded file to a temp location
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.name)[1], dir=temp_dir) as temp_file:
                for chunk in attachment.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            logger.debug(f"Temporary file created: {temp_file_path}")
            logger.debug(f"File readable: {os.access(temp_file_path, os.R_OK)} | File writable: {os.access(temp_file_path, os.W_OK)}")

            if attachment.content_type == "application/pdf":
                logger.debug("Starting PDF-to-image conversion")
                images = convert_from_path(temp_file_path, output_folder=temp_dir)
                text = ""
                for i, image in enumerate(images, 1):
                    logger.debug(f"Running OCR on PDF page {i}")
                    # Save image to temp to bypass WinError 5
                    with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".jpg", delete=False) as img_tmp:
                        image.save(img_tmp.name)
                        page_text = pytesseract.image_to_string(Image.open(img_tmp.name))
                        os.remove(img_tmp.name)
                    text += f"--- Page {i} ---\n{page_text}\n"
            elif attachment.content_type.startswith("image/"):
                logger.debug("Opening image file")
                image = Image.open(temp_file_path)
                logger.debug("Running OCR on image")
                with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".jpg", delete=False) as img_tmp:
                    image.save(img_tmp.name)
                    text = pytesseract.image_to_string(Image.open(img_tmp.name))
                    os.remove(img_tmp.name)
            else:
                text = "Unsupported file type."
                logger.warning(f"Unsupported content type: {attachment.content_type}")

            processed_text = process_text(text)
            extracted_data.append(processed_text)

        except Exception as e:
            logger.exception(f"Error processing attachment {attachment.name}: {e}")
            extracted_data.append(f"Error processing attachment: {str(e)}")
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f"Temporary file deleted: {temp_file_path}")
                except Exception as del_err:
                    logger.warning(f"Could not delete temp file: {temp_file_path}. Reason: {del_err}")
    else:
        logger.error("No attachment received")

    return extracted_data


# Helper function to extract TIN, address, and declared total from text
@csrf_exempt
def process_text(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    tin_match = re.search(r'TIN\s*[:\-]?\s*(\d{3}[- ]?\d{3}[- ]?\d{3}[- ]?\d{3}|\d{3}[- ]?\d{3}[- ]?\d{3})', text, re.I)
    tin_number = tin_match.group(1).replace(" ", "").replace("-", "") if tin_match else "None"
    address = "Not found"
    address_regex = r'(ADDRESS|SPACE NO|UNIT NO|BLDG|LEVEL|STREET|ST|AVE|FLR|FLOOR|MALL|CITY|BARANGAY)[^\n]+'
    address_lines = []
    address_start_index = -1
    for i, line in enumerate(lines):
        if re.search(address_regex, line, re.I):
            address_start_index = i
            break
    if address_start_index != -1:
        for i in range(address_start_index, len(lines)):
            line = lines[i]
            if re.search(r'TIN|SALES INVOICE|TXN NUMBER|TOTAL|CASHIER', line, re.I):
                break
            address_lines.append(line)
        address = ", ".join(address_lines).replace(", ,", ",").strip()
    else:
        address = " ".join(lines[:5])[:100]
    declared_total = "Not found"
    total_regex = r'TOTAL[^\d]*(\d{1,6}(?:\.\d{1,2})?)'
    total_match = re.search(total_regex, text, re.I)
    if total_match:
        declared_total = total_match.group(1)
    else:
        for line in lines:
            amounts = re.findall(r'(\d{1,6}(?:\.\d{1,2})?)', line)
            for val in amounts:
                if 50 <= float(val) < 1000:
                    declared_total = val
                    break
            if declared_total != "Not found":
                break
    return f"TIN Number: {tin_number}\nAddress: {address}\nDeclared Total: {declared_total}"







