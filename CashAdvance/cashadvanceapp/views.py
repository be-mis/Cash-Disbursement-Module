from django.shortcuts import render, redirect, get_object_or_404
from .models import CashAdvance, Transportation, Meal, Lodging, Purchase, CashReimbursement, CashLiquidation
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
import time
from datetime import datetime
from django.db import DatabaseError
from django.db.models import Count


from django.utils.timezone import localtime
from decimal import Decimal
from django.db.models import Q, F
from django.core.mail import send_mail

from PIL import Image
from pdf2image import convert_from_bytes

import os, io, mimetypes, json, pprint, logging


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

GA = ['Shiela Prado', 'Gian Francisco', 'Jonathan Emmanuel Francisco'] #can use the user id or username once the account is created in presto

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
    'Marle Cua-Chin': 'MIS',
    'Gian Francisco': 'MIS',
    'Jonathan Emmanuel Francisco': 'MIS'
}


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


def rolsi(request):
    return render(request, 'rolsi.html')


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



def calculate_status_counts(queryset):
    counts = DEFAULT_STATUS_COUNTS.copy()
    counts['All'] = queryset.count()
    for item in queryset.values('status').annotate(count=Count('status')):
        key = STATUS_MAPPING.get(item['status'], 'All')
        counts[key] += item['count']
    return counts

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

@csrf_exempt
def ca_dashboard(request):
    data = get_request_user_data(request)
    username = data.get('username')
    user_id = data.get('user_id')
    company = data.get('company')
    position = data.get('position')

    print(f"CA Dashboard params: username={username}, user_id={user_id}, company={company}")

    if not username or not user_id:
        print("Error: Missing username or user_id")
        return render(request, 'cadashboard.html', {'error': 'Missing username or user_id'})

    department = APPROVER_DEPARTMENTS.get(username)
    is_approver = department is not None
    is_ga = username in GA

    if is_approver:
        own = CashAdvance.objects.filter(name=username).exclude(status='draft')
        dept = CashAdvance.objects.filter(department=department).exclude(status='draft')
        queryset = (own | dept).distinct()
    else:
        queryset = CashAdvance.objects.filter(name=username).exclude(status='draft')

    # GA special edit access
    editable_queryset = CashAdvance.objects.none()
    if is_ga:
        own_drafts = CashAdvance.objects.filter(name=username, status='draft')
        others_forprocess = CashAdvance.objects.exclude(name=username).filter(status='forprocess')
        editable_queryset = own_drafts | others_forprocess


    context = {
        'table': serialize_records(queryset),
        'status_counts': calculate_status_counts(queryset),
        **data,
        'is_approver': is_approver,
        'username': username,
        'position': position
    }

    print(f"CA Records (excluding drafts): {queryset.count()}")
    return render(request, 'cadashboard.html', context)


@csrf_exempt
def cr_dashboard(request):
    data = get_request_user_data(request)
    print(f"CR Dashboard params: username={data['username']}, user_id={data['user_id']}, company={data['company']}")

    if not data['username'] or not data['user_id']:
        print("Error: Missing username or user_id")
        return render(request, 'crdashboard.html', {'error': 'Missing username or user_id'})

    department = APPROVER_DEPARTMENTS.get(data['username'])
    is_approver = department is not None

    if is_approver:
        own = CashReimbursement.objects.filter(name=data['username']).exclude(status='draft')
        dept = CashReimbursement.objects.filter(department=department).exclude(status='draft')
        queryset = (own | dept).distinct()
    else:
        queryset = CashReimbursement.objects.filter(name=data['username']).exclude(status='draft')

    context = {
        'table': serialize_records(queryset),
        'status_counts': calculate_status_counts(queryset),
        **data,
        'is_approver': is_approver
    }

    print(f"CR Records (excluding drafts): {queryset.count()}")
    return render(request, 'crdashboard.html', context)


@csrf_exempt
def cl_dashboard(request):
    data = get_request_user_data(request)
    print(f"CL Dashboard params: username={data['username']}, user_id={data['user_id']}, company={data['company']}")

    if not data['username'] or not data['user_id']:
        print("Error: Missing username or user_id")
        return render(request, 'cldashboard.html', {'error': 'Missing username or user_id'})

    username = data['username']
    department = APPROVER_DEPARTMENTS.get(username)
    is_approver = department is not None
    is_ga = username in GA

    if is_approver:
        own = CashLiquidation.objects.filter(name=username).exclude(status='draft')
        dept = CashLiquidation.objects.filter(department=department).exclude(status='draft')
        queryset = (own | dept).distinct()
    else:
        queryset = CashLiquidation.objects.filter(name=username).exclude(status='draft')

    # GA special edit access
    editable_queryset = CashLiquidation.objects.none()
    if is_ga:
        own_drafts = CashLiquidation.objects.filter(name=username, status='draft')
        others_forprocess = CashLiquidation.objects.exclude(name=username).filter(status='forprocess')
        editable_queryset = own_drafts | others_forprocess

    context = {
        'table': serialize_records(queryset),
        'editable': serialize_records(editable_queryset),
        'status_counts': calculate_status_counts(queryset),
        **data,
        'is_approver': is_approver,
        'is_ga': is_ga
    }

    print(f"CL Records (excluding drafts): {queryset.count()}")
    print(f"Editable Records for GA: {editable_queryset.count() if is_ga else 0}")
    return render(request, 'cldashboard.html', context)



'''
Dashboard rendering ends here
'''


##### Email notification Start #####
def send_test_email(request):
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
    recipient_list = ['newbarbizon360@gmail.com']  # Replace with a real email

    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        return HttpResponse('Email sent successfully!')
    except Exception as e:
        return HttpResponse(f'Error sending email: {str(e)}')
##### Email notification End #####

def additem(request):
    new_item = request.GET.get('new_item')
    if new_item:
        itemlist = request.session.get('itemlist', [])
        itemlist.append(new_item)
        request.session['itemlist'] = itemlist  # Save back to session
    return redirect('your-view-name')  # Replace with your view name


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
        ).values('date', 'locFrom', 'locTo', 'amount', 'description')

        meal = Meal.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values('date', 'meal_type', 'amount', 'description')

        lodging = Lodging.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values('check_in', 'check_out', 'amount', 'description')

        # Fetch purchase data without querying date_requested
        purchase = Purchase.objects.filter(
            content_type=content_type,
            object_id=main_record.id
        ).values(
            'purchase_number',
            'particulars',
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


@csrf_exempt
def cashadv(request):
    item = Purchase.objects.order_by('-purchase_number').first()
    purchase_number = (item.purchase_number + 1) if item else 1

    username = request.GET.get("username")
    user_id = request.GET.get("userId")
    user_email = request.GET.get("useremail")
    session_id = request.GET.get("sessionId")
    position = request.GET.get("position")
    company = request.GET.get("company")

    today = datetime.today().strftime('%m/%d/%Y')
    db = "ADVANCE"

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
        "purchase_number": purchase_number,
        "itemlist": itemlist,
        "db": db,
        "draftlist": draftlist,  # included draft entries here
    }

    return render(request, "cashadv.html", context)


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


@csrf_exempt
def saveAdvance(request, table_type):
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

                dept = request.POST.get('dept')
                purpose = request.POST.get('purpose')
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
                for entry in transport_entries:
                    try:
                        Transportation.objects.create(
                            content_type=cash_advance_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from'),
                            locTo=entry.get('to'),
                            description=entry.get('desc'),
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
                            meal_type=entry.get('mealType'),
                            description=entry.get('desc'),
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
                            description=entry.get('desc'),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashAdvance
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Lodging: {e}")
                        return HttpResponse(f"Error creating Lodging: {str(e)}", status=400)

                return HttpResponse(f"Successfully saved cash advance records with status '{status}'.")

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

                    date_needed=date_needed,
                    date_requested=date_requested,

                    purpose=purpose,
                    accountNumber=account_number,
                    paymentMode=payment_mode,
                    status=status,
                    table_type="PurchaseAdvance"
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

    return redirect('cashadvance-page', context)


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

            # Amount parsing function
            def parse_decimal(value):
                try:
                    return Decimal(value) if value else Decimal('0')
                except:
                    return Decimal('0')

            if table_type == 'CashReimbursement':
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
                        Transportation.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            locFrom=entry.get('from', ''),
                            locTo=entry.get('to', ''),
                            description=entry.get('desc', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment  # Save the uploaded file
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Transportation: {e}")
                        return HttpResponse(f"Error creating Transportation: {str(e)}", status=400)

                # Save Meal
                for index, entry in enumerate(meal_entries):
                    try:
                        file_key = f'meal_attachment_{index}'
                        attachment = request.FILES.get(file_key)
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
                        logger.error(f"Failed to create Meal: {e}")
                        return HttpResponse(f"Error creating Meal: {str(e)}", status=400)

                # Save Lodging
                for index, entry in enumerate(lodging_entries):
                    try:
                        file_key = f'lodging_attachment_{index}'
                        attachment = request.FILES.get(file_key)
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
                        logger.error(f"Failed to create Lodging: {e}")
                        return HttpResponse(f"Error creating Lodging: {str(e)}", status=400)

                return HttpResponse(f"Successfully saved cash advance records with status '{status}'.")

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
                        file_key = f'purchase_attachment_{index}'
                        attachment = request.FILES.get(file_key)
                        Purchase.objects.create(
                            content_type=cash_reimbursement_content_type,
                            object_id=main_table.id,
                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=attachment
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Purchase: {e}")
                        return HttpResponse(f"Error creating Purchase: {str(e)}", status=400)

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

            # Amount parsing function
            def parse_decimal(value):
                try:
                    return Decimal(value) if value else Decimal('0')
                except:
                    return Decimal('0')

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

                # Get ContentType for CashAdvance
                cash_liquidation_content_type = ContentType.objects.get_for_model(CashLiquidation)

                # Save Transportation
                for entry in transport_entries:
                    try:
                        Transportation.objects.create(
                            content_type=cash_liquidation_content_type,
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
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,
                            date=entry.get('date'),
                            meal_type=entry.get('mealType'),
                            description=entry.get('desc'),
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
                            content_type=cash_liquidation_content_type,
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

                logger.debug(f"CashLiquidationPurchase - name: {name}, businessUnit: {bu}, userEmail: {user_email}, dept: {dept}")

                # Validate businessUnit
                if not bu:
                    logger.error("businessUnit is empty for CashLiquidation")
                    return HttpResponse("Error: Business Unit is required.", status=400)

                # Create CashLiquidation Purchase
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

                # Save Transportation
                for entry in purchase_entries:
                    try:
                        Purchase.objects.create(
                            content_type=cash_liquidation_content_type,
                            object_id=main_table.id,

                            purchase_number=entry.get('purchase_number', ''),
                            particulars=entry.get('particulars', ''),
                            amount=parse_decimal(entry.get('amount')),
                            attachment=None  # No attachment for CashLiquidation
                        )
                    except Exception as e:
                        logger.error(f"Failed to create Purchase: {e}")
                        return HttpResponse(f"Error creating Purchase: {str(e)}", status=400)

                return HttpResponse(f"Successfully saved cash liquidation purchase records with status '{status}'.")

        except Exception as e:
            logger.error(f"Error creating CashLiquidation: {e}")
            return HttpResponse(f"Error: {str(e)}", status=400)

    return render(request, "cashadv.html", context)


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


@csrf_exempt
def approveRequest(request, main_id, table_type, username, status):
    print(f"APPROVER: {username}")
    try:
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

        # Map table types to models
        model_mapping = {
            'CashAdvance': CashAdvance,
            'PurchaseAdvance': CashAdvance,  # Assuming Purchase uses CashAdvance model
            'PurchaseReimbursement': CashReimbursement,  # Assuming Purchase uses CashAdvance model
            'PurchaseLiquidation': CashLiquidation,  # Assuming Purchase uses CashAdvance model
            'CashReimbursement': CashReimbursement,
            'CashLiquidation': CashLiquidation
        }

        if table_type not in model_mapping:
            return JsonResponse({'status': 'error', 'message': 'Invalid Table Type'}, status=400)

        # Fetch the record
        model = model_mapping[table_type]
        main_record = get_object_or_404(model, id=main_id)

        # Prevent self-approval
        if hasattr(main_record, 'requester_username') and main_record.requester_username == username:
            return JsonResponse({'status': 'error', 'message': 'Cannot approve your own request'}, status=403)

        # Get valid statuses for the table type
        valid_statuses = STATUS_TRANSITIONS.get(table_type, [])
        if main_record.status not in valid_statuses:
            return JsonResponse({'status': 'error', 'message': 'Invalid current status'}, status=400)

        # Determine the next status based on user role
        current_status_index = valid_statuses.index(main_record.status)
        if current_status_index + 1 >= len(valid_statuses):
            return JsonResponse({'status': 'error', 'message': 'No further status transitions available'}, status=400)

        next_status = valid_statuses[current_status_index + 1]

        # Restrict status transitions based on user role
        if username in GA:
            if next_status not in ['forrelease', 'pendingliquidation', 'completed']:
                return JsonResponse({'status': 'error', 'message': 'GA user not authorized for this transition'}, status=403)
        elif username in APPROVER_DEPARTMENTS:
            if next_status != 'forprocess':
                return JsonResponse({'status': 'error', 'message': 'Department approver not authorized for this transition'}, status=403)
        else:
            return JsonResponse({'status': 'error', 'message': 'User not authorized to approve'}, status=403)

        # Update the status
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



@csrf_exempt
def rejectRequest(request, main_id, table_type, username):
    try:
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

        if table_type in ['CashAdvance', 'PurchaseAdvance']:
            main_record = get_object_or_404(CashAdvance, id=main_id, table_type=table_type)
        elif table_type in ['CashReimbursement', 'PurchaseReimbursement']:
            main_record = get_object_or_404(CashReimbursement, id=main_id)
        elif table_type in ['CashLiquidation', 'PurchaseLiquidation']:
            main_record = get_object_or_404(CashLiquidation, id=main_id)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid Table Type'}, status=400)

        try:
            data = json.loads(request.body)
            reason = data.get('rejectionReason', '')
        except json.JSONDecodeError:
            reason = ''

        main_record.status = 'denied'

        
        main_record.rejection_reason = reason  # Assumes a rejection_reason field in the model
        main_record.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Request rejected successfully'
        }, status=200)

    except (CashAdvance.DoesNotExist, CashReimbursement.DoesNotExist, CashLiquidation.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



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

# cash_reimbursement = CashReimbursement.objects.get(id=2)
# liquidation = cash_reimbursement.liquidation  # This will return the related CashLiquidation



@csrf_exempt
def updateRecord(request, id, table_type):
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

    # Map table type to model and fetch the record
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
                'attachment': item.attachment.name if item.attachment else ''
            } for item in transportation
        ]
        meal_list = [
            {
                'id': item.id,
                'date': item.date.strftime('%Y-%m-%d') if item.date else '',
                'mealType': item.meal_type,
                'desc': item.description,
                'amount': str(item.amount),
                'attachment': item.attachment.name if item.attachment else ''
            } for item in meal
        ]
        lodging_list = [
            {
                'id': item.id,
                'checkIn': item.check_in.strftime('%Y-%m-%d') if item.check_in else '',
                'checkOut': item.check_out.strftime('%Y-%m-%d') if item.check_out else '',
                'desc': item.description,
                'amount': str(item.amount),
                'attachment': item.attachment.name if item.attachment else ''
            } for item in lodging
        ]
        purchase_list = [
            {
                'id': item.id,
                'purchase_number': item.purchase_number,
                'particulars': item.particulars,
                'amount': str(item.amount),
                'attachment': item.attachment.name if item.attachment else ''
            } for item in purchase
        ]

        purchase_total = sum(item.amount for item in purchase if item.amount) if purchase else 0

        today = datetime.today().strftime('%Y-%m-%d')
        # Prepare data for template
        data = {
            'main': {
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
            'purchase_total': purchase_total,
            'today': today,
            'db': db
        }
        return render(request, 'update.html', data)

    logger.error(f"Method not allowed: {request.method}")
    return redirect('ca_dashboard')


def updateTravel(request):
    pass


def updatePurchase(request):
    pass









