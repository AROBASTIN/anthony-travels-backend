from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from bson.objectid import ObjectId
import datetime

# Import database collections and health utilities
from .db import (
    users_col, drivers_col, cab_owners_col, admins_col,
    vehicles_col, bookings_col, payments_col, reviews_col,
    faqs_col, notifications_col, trip_history_col, fuel_prices_col,
    pricing_config_col, website_content_col, kyc_documents_col,
    verification_requests_col, enquiries_col, ping
)

# Import auth utilities
from .auth import generate_tokens, token_required, role_required, make_password, check_password, decode_jwt_token

# Helpers for MongoDB document serialization
def serialize_doc(doc):
    if not doc:
        return None
    doc = dict(doc)
    if '_id' in doc:
        doc['id'] = str(doc['_id'])
        del doc['_id']
    # Convert datetime fields to iso strings
    for k, v in doc.items():
        if isinstance(v, (datetime.datetime, datetime.date)):
            doc[k] = v.isoformat()
    return doc

def serialize_list(docs):
    return [serialize_doc(doc) for doc in docs]


# --- Database Health Check ---

@api_view(['GET'])
def health_check_view(request):
    """
    GET /api/health
    Returns MongoDB Atlas connection status. No authentication required.
    """
    result = ping()
    http_status = status.HTTP_200_OK if result.get('status') == 'connected' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(result, status=http_status)


# --- Authentication APIs ---

@api_view(['POST'])
def register_view(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    role = data.get('role', 'customer') # customer, driver, cab_owner, admin
    phone = data.get('phone', '')

    if not email or not password or not name:
        return Response({'error': 'Name, email, and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Check if user already exists
    if users_col.find_one({'email': email.lower()}):
        return Response({'error': 'Email is already registered'}, status=status.HTTP_400_BAD_REQUEST)

    # Insert user
    user_doc = {
        'name': name,
        'email': email.lower(),
        'password': make_password(password),
        'role': role,
        'phone': phone,
        'status': 'active', # active, suspended
        'created_at': datetime.datetime.utcnow()
    }
    result = users_col.insert_one(user_doc)
    user_id = result.inserted_id

    # If registering as a driver, seed driver details
    if role == 'driver':
        driver_doc = {
            'user_id': str(user_id),
            'name': name,
            'experience': int(data.get('experience', 2)),
            'languages': data.get('languages', ['Hindi', 'English']),
            'rating': 5.0,
            'status': 'available',
            'verified': False,
            'documents': {
                'license': {'status': 'pending', 'file': ''},
                'aadhar': {'status': 'pending', 'file': ''}
            }
        }
        drivers_col.insert_one(driver_doc)

    return Response({'message': f'User registered successfully as {role}'}, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def login_view(request):
    data = request.data
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    user = users_col.find_one({'email': email.lower()})
    if not user or not check_password(password, user['password']):
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if user.get('status') == 'suspended':
        return Response({'error': 'Your account has been suspended. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)

    access_token, refresh_token = generate_tokens(user['_id'], user['email'], user['role'], user['name'])

    return Response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': str(user['_id']),
            'email': user['email'],
            'name': user['name'],
            'role': user['role'],
            'phone': user.get('phone', '')
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def refresh_token_view(request):
    """
    Accepts a refresh token and returns a new access and refresh token pair.
    """
    data = request.data
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    decoded = decode_jwt_token(refresh_token)
    if not decoded or decoded.get('token_type') != 'refresh':
        return Response({'error': 'Invalid or expired refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        
    user_id = decoded.get('user_id')
    user = users_col.find_one({'_id': ObjectId(user_id)})
    
    if not user or user.get('status') == 'suspended':
        return Response({'error': 'User not found or suspended'}, status=status.HTTP_401_UNAUTHORIZED)
        
    new_access, new_refresh = generate_tokens(user['_id'], user['email'], user['role'], user['name'])
    
    return Response({
        'access_token': new_access,
        'refresh_token': new_refresh
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'PUT'])
@token_required
def profile_view(request):
    if request.method == 'GET':
        user = users_col.find_one({'_id': ObjectId(request.user_id)})
        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_doc(user), status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        data = request.data
        update_fields = {}
        if 'name' in data:
            update_fields['name'] = data['name']
        if 'phone' in data:
            update_fields['phone'] = data['phone']
        
        if not update_fields:
            return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)
        
        users_col.update_one({'_id': ObjectId(request.user_id)}, {'$set': update_fields})
        return Response({'message': 'Profile updated successfully'}, status=status.HTTP_200_OK)


# --- Vehicles APIs ---

@api_view(['GET', 'POST'])
def vehicles_list_view(request):
    if request.method == 'GET':
        category = request.query_params.get('category')
        query = {}
        if category:
            query['category'] = category

        # Extract role to determine if unapproved vehicles should be hidden
        auth_header = request.headers.get('Authorization', None)
        role = None
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                decoded = decode_jwt_token(parts[1])
                if decoded:
                    role = decoded.get('role')
        
        # Only admin and cab owners can see unapproved vehicles
        if role not in ['admin', 'cab_owner']:
            query['approved'] = True

        vehicles = vehicles_col.find(query)
        return Response(serialize_list(vehicles), status=status.HTTP_200_OK)

    elif request.method == 'POST':
        # Requires Cab Owner or Admin role
        @role_required(['cab_owner', 'admin'])
        def handle_post(req):
            if req.user_role == 'cab_owner':
                owner_user = users_col.find_one({'_id': ObjectId(req.user_id)})
                if not owner_user or owner_user.get('kyc_status') != 'Approved':
                    return Response({'error': 'Your KYC must be Approved before you can add vehicles to the fleet.'}, status=status.HTTP_403_FORBIDDEN)

            data = req.data
            name = data.get('name')
            category = data.get('category')
            plate_number = data.get('plate_number')
            seats = int(data.get('seats', 4))
            price_per_km = float(data.get('price_per_km', 12.0))
            fuel = data.get('fuel', 'Petrol')
            ac = data.get('ac', True)
            driver_available = data.get('driver_available', True)

            if not name or not category or not plate_number:
                return Response({'error': 'Name, category, and plate number are required'}, status=status.HTTP_400_BAD_REQUEST)

            # Auto-approve if created by admin, otherwise needs admin approval
            is_approved = (req.user_role == 'admin')

            vehicle_doc = {
                'name': name,
                'category': category,
                'plate_number': plate_number,
                'seats': seats,
                'price_per_km': price_per_km,
                'fuel': fuel,
                'ac': ac,
                'driver_available': driver_available,
                'owner_id': req.user_id,
                'status': 'available',
                'rating': 5.0,
                'reviews': 0,
                'approved': is_approved
            }
            vehicles_col.insert_one(vehicle_doc)
            return Response({'message': 'Vehicle added successfully', 'approved': is_approved}, status=status.HTTP_201_CREATED)

        return handle_post(request)

@api_view(['GET', 'PUT', 'DELETE'])
def vehicle_detail_view(request, vehicle_id):
    try:
        obj_id = ObjectId(vehicle_id)
    except:
        return Response({'error': 'Invalid vehicle ID format'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        vehicle = vehicles_col.find_one({'_id': obj_id})
        if not vehicle:
            return Response({'error': 'Vehicle not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_doc(vehicle), status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        @role_required(['cab_owner', 'admin'])
        def handle_put(req):
            if req.user_role == 'cab_owner':
                owner_user = users_col.find_one({'_id': ObjectId(req.user_id)})
                if not owner_user or owner_user.get('kyc_status') != 'Approved':
                    return Response({'error': 'Your KYC must be Approved before you can modify vehicles.'}, status=status.HTTP_403_FORBIDDEN)

            data = req.data
            update_fields = {}
            for field in ['name', 'category', 'plate_number', 'seats', 'price_per_km', 'fuel', 'ac', 'driver_available', 'status', 'approved']:
                if field in data:
                    update_fields[field] = data[field]
            
            if 'seats' in update_fields:
                update_fields['seats'] = int(update_fields['seats'])
            if 'price_per_km' in update_fields:
                update_fields['price_per_km'] = float(update_fields['price_per_km'])
            
            vehicles_col.update_one({'_id': obj_id}, {'$set': update_fields})
            return Response({'message': 'Vehicle updated successfully'}, status=status.HTTP_200_OK)

        return handle_put(request)

    elif request.method == 'DELETE':
        @role_required(['cab_owner', 'admin'])
        def handle_delete(req):
            vehicles_col.delete_one({'_id': obj_id})
            return Response({'message': 'Vehicle deleted successfully'}, status=status.HTTP_200_OK)

        return handle_delete(request)


# --- Drivers APIs ---

@api_view(['GET'])
@token_required
def drivers_list_view(request):
    if request.user_role not in ['cab_owner', 'admin']:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    
    drivers = drivers_col.find()
    return Response(serialize_list(drivers), status=status.HTTP_200_OK)

@api_view(['PUT'])
@token_required
def driver_document_view(request, driver_id):
    # Only the driver themselves or admin can upload/update documents
    if request.user_role != 'admin':
        driver = drivers_col.find_one({'_id': ObjectId(driver_id)})
        if not driver or driver.get('user_id') != request.user_id:
            return Response({'error': 'Unauthorized to modify this driver profile'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    doc_type = data.get('doc_type') # license, aadhar
    doc_status = data.get('status', 'uploaded') # uploaded, verified, rejected

    if doc_type not in ['license', 'aadhar']:
        return Response({'error': 'Invalid document type. Use license or aadhar'}, status=status.HTTP_400_BAD_REQUEST)

    update_key = f'documents.{doc_type}.status'
    drivers_col.update_one({'_id': ObjectId(driver_id)}, {'$set': {update_key: doc_status}})
    
    # If both license and aadhar are verified, mark driver as verified
    driver = drivers_col.find_one({'_id': ObjectId(driver_id)})
    if (driver.get('documents', {}).get('license', {}).get('status') == 'verified' and 
        driver.get('documents', {}).get('aadhar', {}).get('status') == 'verified'):
        drivers_col.update_one({'_id': ObjectId(driver_id)}, {'$set': {'verified': True}})
        
    return Response({'message': 'Driver documents updated'}, status=status.HTTP_200_OK)


# --- Bookings APIs ---

@api_view(['GET', 'POST'])
@token_required
def bookings_list_view(request):
    if request.method == 'GET':
        role = request.user_role
        user_id = request.user_id

        if role == 'customer':
            bookings = bookings_col.find({'customer_id': user_id})
        elif role == 'driver':
            bookings = bookings_col.find({'driver_id': user_id})
        elif role == 'cab_owner':
            # Cab owner views bookings for vehicles they own
            my_vehicles = vehicles_col.find({'owner_id': user_id})
            my_vehicle_names = [v['name'] for v in my_vehicles]
            bookings = bookings_col.find({'vehicle': {'$in': my_vehicle_names}})
        elif role == 'admin':
            bookings = bookings_col.find()
        else:
            bookings = []

        return Response(serialize_list(bookings), status=status.HTTP_200_OK)

    elif request.method == 'POST':
        data = request.data
        pickup_location = data.get('pickupLocation')
        drop_location = data.get('dropLocation', '')
        pickup_date = data.get('pickupDate')
        pickup_time = data.get('pickupTime')
        drop_date = data.get('dropDate')
        drop_time = data.get('dropTime')
        vehicle_type = data.get('vehicleType')
        passengers_count = int(data.get('passengersCount', 1))
        driver_required = data.get('driverRequired', True)
        fare_details = data.get('fareDetails')

        if not pickup_location or not pickup_date or not pickup_time or not vehicle_type:
            return Response({'error': 'Missing required booking fields'}, status=status.HTTP_400_BAD_REQUEST)

        # Check customer KYC status
        cust_user = users_col.find_one({'_id': ObjectId(request.user_id)})
        if not cust_user or cust_user.get('kyc_status') != 'Approved':
            return Response({'error': 'Your KYC must be Approved before you can book trips.'}, status=status.HTTP_403_FORBIDDEN)

        # Select a mock available driver if needed
        assigned_driver_id = None
        assigned_driver_name = None
        if driver_required:
            available_driver = drivers_col.find_one({'status': 'available', 'verified': True})
            if available_driver:
                assigned_driver_id = available_driver['user_id']
                assigned_driver_name = available_driver['name']
                # Mark driver busy
                drivers_col.update_one({'_id': available_driver['_id']}, {'$set': {'status': 'busy'}})

        booking_doc = {
            'pickupLocation': pickup_location,
            'dropLocation': drop_location,
            'pickupDate': pickup_date,
            'pickupTime': pickup_time,
            'dropDate': drop_date,
            'dropTime': drop_time,
            'vehicleType': vehicle_type,
            'passengersCount': passengers_count,
            'driverRequired': driver_required,
            'customer_id': request.user_id,
            'customer_name': request.user_name,
            'driver_id': assigned_driver_id,
            'driver_name': assigned_driver_name,
            'status': 'pending',
            'fareDetails': fare_details,
            'created_at': datetime.datetime.utcnow()
        }
        result = bookings_col.insert_one(booking_doc)
        inserted_id = str(result.inserted_id)

        # Insert a notification
        notification_doc = {
            'user_id': request.user_id,
            'title': 'Booking Created',
            'message': f'Your ride from {pickup_location} is pending approval.',
            'read': False,
            'created_at': datetime.datetime.utcnow()
        }
        notifications_col.insert_one(notification_doc)

        return Response({
            'message': 'Booking requested successfully',
            'booking_id': inserted_id,
            'assigned_driver': assigned_driver_name
        }, status=status.HTTP_201_CREATED)

@api_view(['PUT'])
@token_required
def booking_status_view(request, booking_id):
    try:
        obj_id = ObjectId(booking_id)
    except:
        return Response({'error': 'Invalid booking ID format'}, status=status.HTTP_400_BAD_REQUEST)

    booking = bookings_col.find_one({'_id': obj_id})
    if not booking:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    new_status = data.get('status') # pending, accepted, rejected, completed, cancelled

    if new_status not in ['pending', 'accepted', 'rejected', 'completed', 'cancelled']:
        return Response({'error': 'Invalid status update request'}, status=status.HTTP_400_BAD_REQUEST)

    # Perform update
    bookings_col.update_one({'_id': obj_id}, {'$set': {'status': new_status}})

    # If trip is completed/cancelled, free up the driver
    if new_status in ['completed', 'cancelled', 'rejected'] and booking.get('driver_id'):
        drivers_col.update_one({'user_id': booking['driver_id']}, {'$set': {'status': 'available'}})

    # Record history if completed or cancelled
    if new_status in ['completed', 'cancelled']:
        history_doc = {
            'booking_id': booking_id,
            'customer_id': booking['customer_id'],
            'driver_id': booking.get('driver_id'),
            'vehicleType': booking['vehicleType'],
            'fare': booking.get('fareDetails', {}).get('finalAmount', 0),
            'status': new_status,
            'completed_at': datetime.datetime.utcnow()
        }
        trip_history_col.insert_one(history_doc)

    return Response({'message': f'Booking status updated to {new_status}'}, status=status.HTTP_200_OK)


# --- Payment APIs ---

@api_view(['POST'])
@token_required
def payments_checkout_view(request):
    data = request.data
    booking_id = data.get('booking_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'UPI')

    if not booking_id or not amount:
        return Response({'error': 'Booking ID and amount are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Simulate payment success
    transaction_id = f'TXN-{int(datetime.datetime.utcnow().timestamp() * 1000)}'
    payment_doc = {
        'booking_id': booking_id,
        'customer_id': request.user_id,
        'amount': float(amount),
        'payment_method': payment_method,
        'status': 'success',
        'transaction_id': transaction_id,
        'created_at': datetime.datetime.utcnow()
    }
    payments_col.insert_one(payment_doc)

    # Update booking status to confirmed/accepted
    bookings_col.update_one({'_id': ObjectId(booking_id)}, {'$set': {'status': 'accepted', 'payment_status': 'paid'}})

    return Response({
        'message': 'Payment processed successfully',
        'transaction_id': transaction_id,
        'status': 'success'
    }, status=status.HTTP_200_OK)


# --- Reviews and FAQs ---

@api_view(['GET', 'POST'])
def reviews_view(request):
    if request.method == 'GET':
        reviews = reviews_col.find().sort('created_at', -1).limit(20)
        return Response(serialize_list(reviews), status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        @token_required
        def handle_post(req):
            data = req.data
            rating = int(data.get('rating', 5))
            comment = data.get('comment', '')

            if not comment:
                return Response({'error': 'Comment is required'}, status=status.HTTP_400_BAD_REQUEST)

            review_doc = {
                'customer_name': req.user_name,
                'customer_id': req.user_id,
                'rating': rating,
                'comment': comment,
                'created_at': datetime.datetime.utcnow()
            }
            reviews_col.insert_one(review_doc)
            return Response({'message': 'Review added successfully'}, status=status.HTTP_201_CREATED)
        
        return handle_post(request)

@api_view(['GET'])
def faqs_view(request):
    faqs = faqs_col.find()
    return Response(serialize_list(faqs), status=status.HTTP_200_OK)


# --- Fuel Prices ---

@api_view(['GET', 'PUT'])
def fuel_prices_view(request):
    if request.method == 'GET':
        prices = fuel_prices_col.find_one()
        if not prices:
            # Fallback mock default
            prices = {'petrol': 103.44, 'diesel': 89.79}
        return Response(serialize_doc(prices), status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        @role_required('admin')
        def handle_put(req):
            data = req.data
            petrol = float(data.get('petrol'))
            diesel = float(data.get('diesel'))

            fuel_prices_col.update_one({}, {'$set': {'petrol': petrol, 'diesel': diesel}}, upsert=True)
            return Response({'message': 'Fuel prices updated successfully'}, status=status.HTTP_200_OK)
        
        return handle_put(request)


# --- Dashboard Stats ---

@api_view(['GET'])
@token_required
def dashboard_stats_view(request):
    role = request.user_role
    user_id = request.user_id

    stats = {}
    if role == 'customer':
        total_bookings = bookings_col.count_documents({'customer_id': user_id})
        pending = bookings_col.count_documents({'customer_id': user_id, 'status': 'pending'})
        active = bookings_col.count_documents({'customer_id': user_id, 'status': 'accepted'})
        completed = bookings_col.count_documents({'customer_id': user_id, 'status': 'completed'})
        
        # Calculate spent
        spent = 0
        customer_payments = payments_col.find({'customer_id': user_id, 'status': 'success'})
        for p in customer_payments:
            spent += p.get('amount', 0)

        stats = {
            'total_bookings': total_bookings,
            'pending_bookings': pending,
            'active_bookings': active,
            'completed_bookings': completed,
            'total_spent': spent
        }

    elif role == 'driver':
        driver_jobs = bookings_col.find({'driver_id': user_id})
        total_trips = bookings_col.count_documents({'driver_id': user_id})
        assigned = bookings_col.count_documents({'driver_id': user_id, 'status': 'pending'})
        active = bookings_col.count_documents({'driver_id': user_id, 'status': 'accepted'})
        completed = bookings_col.count_documents({'driver_id': user_id, 'status': 'completed'})
        
        # Driver earnings
        earnings = completed * 400

        driver_profile = drivers_col.find_one({'user_id': user_id})
        stats = {
            'total_trips': total_trips,
            'assigned_trips': assigned,
            'active_trips': active,
            'completed_trips': completed,
            'total_earnings': earnings,
            'verified': driver_profile.get('verified', False) if driver_profile else False
        }

    elif role == 'cab_owner':
        my_vehicles = list(vehicles_col.find({'owner_id': user_id}))
        vehicle_names = [v['name'] for v in my_vehicles]
        
        fleet_size = len(my_vehicles)
        total_bookings = bookings_col.count_documents({'vehicle': {'$in': vehicle_names}})
        
        # Calculate revenue
        revenue = 0
        bookings = bookings_col.find({'vehicle': {'$in': vehicle_names}, 'status': 'completed'})
        for b in bookings:
            revenue += b.get('fareDetails', {}).get('finalAmount', 0)

        stats = {
            'fleet_size': fleet_size,
            'total_bookings': total_bookings,
            'total_revenue': revenue
        }

    elif role == 'admin':
        users_count = users_col.count_documents({})
        vehicles_count = vehicles_col.count_documents({})
        bookings_count = bookings_col.count_documents({})
        
        # Total revenue
        revenue = 0
        payments = payments_col.find({'status': 'success'})
        for p in payments:
            revenue += p.get('amount', 0)

        stats = {
            'users_count': users_count,
            'vehicles_count': vehicles_count,
            'bookings_count': bookings_count,
            'total_revenue': revenue
        }

    return Response(stats, status=status.HTTP_200_OK)


# ==========================================
# --- ADMIN SUPER CONTROL PANELS APIs ------
# ==========================================

@api_view(['GET', 'PUT'])
def admin_pricing_view(request):
    """
    Get or Update global pricing parameters.
    """
    if request.method == 'GET':
        config = pricing_config_col.find_one()
        if not config:
            config = {}
        config.setdefault("base_rent", {
            "hatchback": 1200, "sedan": 1600, "suv": 2200, 
            "crysta": 3200, "traveller": 4500, "minibus": 6500, "luxury": 10000
        })
        config.setdefault("km_rates", {
            "hatchback": 12, "sedan": 14, "suv": 16, 
            "crysta": 22, "traveller": 26, "minibus": 35, "luxury": 50
        })
        config.setdefault("driver_salary", 400)
        config.setdefault("convenience_fee", 25)
        config.setdefault("platform_fee", 99)
        config.setdefault("gst_percent", 5)
        config.setdefault("fuel_cost_formula", 1.1)
        config.setdefault("toll_multiplier", 1.0)
        config.setdefault("night_charges", 250)
        config.setdefault("festival_charges", 300)
        config.setdefault("seasonal_pricing", 1.15)
        config.setdefault("min_booking_amount", 500)
        config.setdefault("offers_enabled", True)
        return Response(serialize_doc(config), status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        @role_required('admin')
        def handle_put(req):
            data = req.data
            pricing_config_col.update_one({}, {'$set': data}, upsert=True)
            return Response({'message': 'Pricing configuration updated successfully'}, status=status.HTTP_200_OK)
        return handle_put(request)

@api_view(['GET', 'PUT'])
def admin_content_view(request):
    """
    Get or Update website banner text and company info.
    """
    if request.method == 'GET':
        content = website_content_col.find_one()
        if not content:
            content = {
                "hero_title": "Premium Outstation & Local Cab Service",
                "hero_subtitle": "Anthony Travels provides transparent pricing, verified professional drivers, and top-tier cars for a premium travel experience across India.",
                "company_info": "Anthony Travels is a premier travel booking service designed for Indian customers, offering car rentals, outstation trips, airport transfers, and corporate travel.",
                "contact_phone": "+91 99999 88888",
                "contact_email": "bookings@anthonytravels.com",
                "contact_address": "Anthony Travels HQ, Suite 404, Cyber City, Gurugram, India"
            }
        return Response(serialize_doc(content), status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        @role_required('admin')
        def handle_put(req):
            data = req.data
            website_content_col.update_one({}, {'$set': data}, upsert=True)
            return Response({'message': 'Website content configuration saved successfully'}, status=status.HTTP_200_OK)
        return handle_put(request)

@api_view(['GET'])
@role_required('admin')
def admin_users_view(request):
    """
    List all user accounts in the database.
    """
    users = users_col.find()
    return Response(serialize_list(users), status=status.HTTP_200_OK)

@api_view(['PUT', 'DELETE'])
@role_required('admin')
def admin_user_detail_view(request, user_id):
    """
    Modify or Delete a user account (includes suspension).
    """
    try:
        obj_id = ObjectId(user_id)
    except:
        return Response({'error': 'Invalid user ID format'}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'PUT':
        data = request.data
        update_fields = {}
        for field in ['name', 'phone', 'role', 'status']:
            if field in data:
                update_fields[field] = data[field]
        
        res = users_col.update_one({'_id': obj_id}, {'$set': update_fields})
        if res.matched_count == 0:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': 'User profile updated successfully'}, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        res = users_col.delete_one({'_id': obj_id})
        if res.deleted_count == 0:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        # If it was a driver, clear driver meta as well
        drivers_col.delete_many({'user_id': user_id})
        return Response({'message': 'User deleted successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
@role_required('admin')
def admin_drivers_view(request):
    """
    Add a new driver.
    """
    data = request.data
    email = data.get('email')
    password = data.get('password', 'password123')
    name = data.get('name')
    phone = data.get('phone', '')

    if not email or not name:
        return Response({'error': 'Name and Email are required'}, status=status.HTTP_400_BAD_REQUEST)

    if users_col.find_one({'email': email.lower()}):
        return Response({'error': 'Email is already in use'}, status=status.HTTP_400_BAD_REQUEST)

    user_doc = {
        'name': name,
        'email': email.lower(),
        'password': make_password(password),
        'role': 'driver',
        'phone': phone,
        'status': 'active',
        'created_at': datetime.datetime.utcnow()
    }
    result = users_col.insert_one(user_doc)
    user_id = result.inserted_id

    driver_doc = {
        'user_id': str(user_id),
        'name': name,
        'experience': int(data.get('experience', 2)),
        'languages': data.get('languages', ['Hindi', 'English']),
        'rating': 5.0,
        'status': 'available',
        'verified': True,
        'documents': {
            'license': {'status': 'verified', 'file': ''},
            'aadhar': {'status': 'verified', 'file': ''}
        }
    }
    drivers_col.insert_one(driver_doc)

    return Response({'message': 'Driver account created successfully'}, status=status.HTTP_201_CREATED)

@api_view(['PUT', 'DELETE'])
@role_required('admin')
def admin_driver_detail_view(request, driver_id):
    """
    Edit details or delete a driver.
    """
    try:
        obj_id = ObjectId(driver_id)
    except:
        return Response({'error': 'Invalid driver ID format'}, status=status.HTTP_400_BAD_REQUEST)

    driver = drivers_col.find_one({'_id': obj_id})
    if not driver:
        return Response({'error': 'Driver profile not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PUT':
        data = request.data
        update_fields = {}
        for field in ['name', 'experience', 'languages', 'rating', 'status', 'verified']:
            if field in data:
                update_fields[field] = data[field]
        
        if 'experience' in update_fields:
            update_fields['experience'] = int(update_fields['experience'])
        if 'rating' in update_fields:
            update_fields['rating'] = float(update_fields['rating'])

        drivers_col.update_one({'_id': obj_id}, {'$set': update_fields})

        # Sync base user account name/status
        user_updates = {}
        if 'name' in data:
            user_updates['name'] = data['name']
        if 'status' in data:
            user_updates['status'] = 'suspended' if data['status'] == 'suspended' else 'active'
        
        if user_updates:
            users_col.update_one({'_id': ObjectId(driver['user_id'])}, {'$set': user_updates})

        return Response({'message': 'Driver profile modified successfully'}, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        drivers_col.delete_one({'_id': obj_id})
        users_col.delete_one({'_id': ObjectId(driver['user_id'])})
        return Response({'message': 'Driver deleted successfully'}, status=status.HTTP_200_OK)

@api_view(['PUT'])
@role_required('admin')
def admin_booking_detail_view(request, booking_id):
    """
    Modify trip parameters (locations, pricing, driver assignment, or statuses).
    """
    try:
        obj_id = ObjectId(booking_id)
    except:
        return Response({'error': 'Invalid booking ID format'}, status=status.HTTP_400_BAD_REQUEST)

    booking = bookings_col.find_one({'_id': obj_id})
    if not booking:
        return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    update_fields = {}
    
    # Pricing overrides, driver reassignment, status changes
    for field in ['pickupLocation', 'dropLocation', 'pickupDate', 'pickupTime', 'dropDate', 'dropTime', 'vehicleType', 'passengersCount', 'driverRequired', 'status', 'driver_id', 'driver_name', 'fareDetails']:
        if field in data:
            update_fields[field] = data[field]

    if 'passengersCount' in update_fields:
        update_fields['passengersCount'] = int(update_fields['passengersCount'])
        
    bookings_col.update_one({'_id': obj_id}, {'$set': update_fields})
    return Response({'message': 'Booking modified successfully'}, status=status.HTTP_200_OK)

@api_view(['POST'])
@role_required('admin')
def admin_vehicle_approve_view(request, vehicle_id):
    """
    Approve a vehicle listed by a Cab Owner.
    """
    try:
        obj_id = ObjectId(vehicle_id)
    except:
        return Response({'error': 'Invalid vehicle ID format'}, status=status.HTTP_400_BAD_REQUEST)

    vehicles_col.update_one({'_id': obj_id}, {'$set': {'approved': True}})
    return Response({'message': 'Vehicle approved successfully and is now active'}, status=status.HTTP_200_OK)



# --- KYC VERIFICATION SYSTEM APIS ---
import os
import uuid
from django.conf import settings
from django.core.files.storage import FileSystemStorage

@api_view(['GET'])
@token_required
def kyc_status_view(request):
    """
    GET /api/kyc/status
    Get the logged-in user's KYC documents and general KYC verification status.
    """
    user_id = request.user_id
    user = users_col.find_one({'_id': ObjectId(user_id)})
    if not user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    docs = list(kyc_documents_col.find({'user_id': user_id}))
    serialized_docs = serialize_list(docs)
    
    return Response({
        'kyc_status': user.get('kyc_status', 'None'),
        'documents': serialized_docs,
        'role': user.get('role')
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@token_required
def kyc_upload_view(request):
    """
    POST /api/kyc/upload
    Upload a KYC document file for the logged-in user.
    """
    user_id = request.user_id
    user = users_col.find_one({'_id': ObjectId(user_id)})
    if not user:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
    role = user.get('role', 'customer')
    doc_type = request.data.get('doc_type')
    uploaded_file = request.FILES.get('file')
    
    if not doc_type or not uploaded_file:
        return Response({'error': 'doc_type and file are required'}, status=status.HTTP_400_BAD_REQUEST)
        
    role_docs = {
        'customer': ['profile_picture', 'aadhar_front', 'aadhar_back'],
        'driver': ['profile_picture', 'aadhar_front', 'aadhar_back', 'license_front', 'license_back'],
        'cab_owner': ['profile_picture', 'aadhar_front', 'aadhar_back', 'pan_card', 'rc_book', 'insurance', 'vehicle_photos']
    }
    
    allowed_types = role_docs.get(role, [])
    if doc_type not in allowed_types:
        return Response({'error': f'Invalid doc_type for role {role}. Allowed: {allowed_types}'}, status=status.HTTP_400_BAD_REQUEST)
        
    # Save the file securely
    fs_dir = os.path.join(settings.MEDIA_ROOT, 'kyc')
    if not os.path.exists(fs_dir):
        os.makedirs(fs_dir, exist_ok=True)
        
    file_ext = os.path.splitext(uploaded_file.name)[1]
    filename = f"{user_id}_{doc_type}_{uuid.uuid4().hex[:8]}{file_ext}"
    
    fs = FileSystemStorage(location=fs_dir)
    saved_name = fs.save(filename, uploaded_file)
    file_url = request.build_absolute_uri(settings.MEDIA_URL + 'kyc/' + saved_name)
    
    # Store or update file metadata in MongoDB
    doc_meta = {
        'user_id': user_id,
        'doc_type': doc_type,
        'filename': saved_name,
        'file_url': file_url,
        'status': 'uploaded',
        'uploaded_at': datetime.datetime.utcnow()
    }
    
    kyc_documents_col.update_one(
        {'user_id': user_id, 'doc_type': doc_type},
        {'$set': doc_meta},
        upsert=True
    )
    
    # Check if all mandatory documents have been uploaded
    docs_cursor = kyc_documents_col.find({'user_id': user_id})
    uploaded_types = [d['doc_type'] for d in docs_cursor]
    missing = [t for t in allowed_types if t not in uploaded_types]
    
    if not missing:
        # Update user status to Pending review
        users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'kyc_status': 'Pending'}})
        
        # Create or update verification request
        req_doc = {
            'user_id': user_id,
            'name': user.get('name'),
            'email': user.get('email'),
            'role': role,
            'status': 'Pending',
            'updated_at': datetime.datetime.utcnow()
        }
        verification_requests_col.update_one(
            {'user_id': user_id},
            {'$set': req_doc},
            upsert=True
        )
    else:
        # Keep user status as incomplete/Rejected/None until all are uploaded
        current_status = user.get('kyc_status', 'None')
        if current_status != 'Pending' and current_status != 'Approved':
            users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'kyc_status': 'Incomplete'}})
            
    return Response({
        'message': f'Document {doc_type} uploaded successfully',
        'file_url': file_url,
        'missing_documents': missing
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@role_required('admin')
def admin_kyc_list_view(request):
    """
    GET /api/admin/kyc/requests
    Fetch all verification requests for the admin.
    """
    requests = list(verification_requests_col.find().sort('updated_at', -1))
    serialized_reqs = serialize_list(requests)
    
    # Populate documents for each request
    for req in serialized_reqs:
        docs = list(kyc_documents_col.find({'user_id': req['user_id']}))
        req['documents'] = serialize_list(docs)
        
    return Response(serialized_reqs, status=status.HTTP_200_OK)

@api_view(['POST'])
@role_required('admin')
def admin_kyc_action_view(request, request_id):
    """
    POST /api/admin/kyc/requests/<str:request_id>/action
    Approve, Reject, or Request re-upload.
    """
    try:
        req_obj_id = ObjectId(request_id)
    except:
        return Response({'error': 'Invalid request ID format'}, status=status.HTTP_400_BAD_REQUEST)
        
    req = verification_requests_col.find_one({'_id': req_obj_id})
    if not req:
        return Response({'error': 'Verification request not found'}, status=status.HTTP_404_NOT_FOUND)
        
    user_id = req['user_id']
    action = request.data.get('action') # approve, reject, request_reupload
    notes = request.data.get('notes', '')
    
    if action not in ['approve', 'reject', 'request_reupload']:
        return Response({'error': 'Invalid action. Must be approve, reject, or request_reupload'}, status=status.HTTP_400_BAD_REQUEST)
        
    if action == 'approve':
        # Approve all documents
        kyc_documents_col.update_many({'user_id': user_id}, {'$set': {'status': 'Approved'}})
        # Update verification request
        verification_requests_col.update_one({'_id': req_obj_id}, {'$set': {'status': 'Approved', 'notes': notes, 'updated_at': datetime.datetime.utcnow()}})
        # Update user profile
        users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'kyc_status': 'Approved'}})
        # If driver, update driver verified status
        if req.get('role') == 'driver':
            drivers_col.update_one({'user_id': user_id}, {'$set': {'verified': True}})
            
        notification_doc = {
            'user_id': user_id,
            'title': 'KYC Verification Approved',
            'message': 'Congratulations! Your KYC verification request has been approved. You can now access all services.',
            'read': False,
            'created_at': datetime.datetime.utcnow()
        }
        notifications_col.insert_one(notification_doc)
        
    elif action == 'reject':
        # Reject all documents
        kyc_documents_col.update_many({'user_id': user_id}, {'$set': {'status': 'Rejected'}})
        # Update request
        verification_requests_col.update_one({'_id': req_obj_id}, {'$set': {'status': 'Rejected', 'notes': notes, 'updated_at': datetime.datetime.utcnow()}})
        # Update user profile
        users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'kyc_status': 'Rejected'}})
        if req.get('role') == 'driver':
            drivers_col.update_one({'user_id': user_id}, {'$set': {'verified': False}})
            
        notification_doc = {
            'user_id': user_id,
            'title': 'KYC Verification Rejected',
            'message': f'Your KYC verification has been rejected. Reason: {notes}',
            'read': False,
            'created_at': datetime.datetime.utcnow()
        }
        notifications_col.insert_one(notification_doc)
        
    elif action == 'request_reupload':
        rejected_docs = request.data.get('doc_types', []) # list of doc_type strings to reject
        if not rejected_docs:
            return Response({'error': 'doc_types list is required for request_reupload action'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Reject specific documents
        kyc_documents_col.update_many(
            {'user_id': user_id, 'doc_type': {'$in': rejected_docs}},
            {'$set': {'status': 'Rejected'}}
        )
        
        # Mark other documents as Approved if they weren't rejected
        kyc_documents_col.update_many(
            {'user_id': user_id, 'doc_type': {'$nin': rejected_docs}},
            {'$set': {'status': 'Approved'}}
        )
        
        # Update request status to Rejected
        verification_requests_col.update_one({'_id': req_obj_id}, {'$set': {'status': 'Rejected', 'notes': notes, 'updated_at': datetime.datetime.utcnow()}})
        users_col.update_one({'_id': ObjectId(user_id)}, {'$set': {'kyc_status': 'Rejected'}})
        if req.get('role') == 'driver':
            drivers_col.update_one({'user_id': user_id}, {'$set': {'verified': False}})
            
        notification_doc = {
            'user_id': user_id,
            'title': 'KYC Action Required: Re-upload Requested',
            'message': f'Please re-upload: {", ".join(rejected_docs)}. Reason: {notes}',
            'read': False,
            'created_at': datetime.datetime.utcnow()
        }
        notifications_col.insert_one(notification_doc)
        
    return Response({'message': f'KYC request processed successfully: {action}'}, status=status.HTTP_200_OK)


# ==========================================
# --- ENQUIRY / BOOKING WORKFLOW APIS ------
# ==========================================

@api_view(['GET', 'POST'])
def enquiries_view(request):
    """
    GET  /api/enquiries  — Admin: list all enquiries with optional search/filter
    POST /api/enquiries  — Public: submit a new travel enquiry
    """
    if request.method == 'POST':
        data = request.data
        # Validate required fields
        required = ['full_name', 'mobile_number', 'pickup_location', 'journey_date', 'vehicle_type']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

        enquiry_doc = {
            # Customer Details
            'full_name':        data.get('full_name', '').strip(),
            'mobile_number':    data.get('mobile_number', '').strip(),
            'email':            data.get('email', '').strip(),
            # Trip Details
            'pickup_location':  data.get('pickup_location', '').strip(),
            'drop_location':    data.get('drop_location', '').strip(),
            'journey_date':     data.get('journey_date', ''),
            'journey_time':     data.get('journey_time', ''),
            'return_date':      data.get('return_date', ''),
            'trip_type':        data.get('trip_type', 'one_way'),  # one_way | round_trip
            # Passenger & Vehicle
            'passengers':       int(data.get('passengers', 1)),
            'bags':             int(data.get('bags', 0)),
            'vehicle_type':     data.get('vehicle_type', ''),
            'ac_required':      bool(data.get('ac_required', True)),
            'driver_required':  bool(data.get('driver_required', True)),
            # Additional (support both message and special_requests keys)
            'special_requests': data.get('special_requests', data.get('message', '')).strip(),
            # Meta
            'status':           'new',          # new | contacted | converted | closed
            'assigned_to':      '',
            'notes':            '',
            'created_at':       datetime.datetime.utcnow(),
            'updated_at':       datetime.datetime.utcnow(),
        }
        result = enquiries_col.insert_one(enquiry_doc)
        return Response({
            'message': 'Enquiry submitted successfully',
            'enquiry_id': str(result.inserted_id)
        }, status=status.HTTP_201_CREATED)

    elif request.method == 'GET':
        @role_required('admin')
        def handle_get(req):
            status_filter = req.query_params.get('status')   # new|contacted|converted|closed
            search        = req.query_params.get('search', '').strip()
            query = {}
            if status_filter and status_filter in ['new', 'contacted', 'converted', 'closed']:
                query['status'] = status_filter
            if search:
                query['$or'] = [
                    {'full_name':        {'$regex': search, '$options': 'i'}},
                    {'mobile_number':    {'$regex': search, '$options': 'i'}},
                    {'email':            {'$regex': search, '$options': 'i'}},
                    {'pickup_location':  {'$regex': search, '$options': 'i'}},
                    {'drop_location':    {'$regex': search, '$options': 'i'}},
                ]
            docs = list(enquiries_col.find(query).sort('created_at', -1).limit(200))
            return Response(serialize_list(docs), status=status.HTTP_200_OK)
        return handle_get(request)


@api_view(['GET', 'PUT'])
def enquiry_detail_view(request, enquiry_id):
    """
    GET /api/enquiries/<id>   — Admin: view single enquiry
    PUT /api/enquiries/<id>   — Admin: update status/notes/assignment
    """
    try:
        obj_id = ObjectId(enquiry_id)
    except Exception:
        return Response({'error': 'Invalid enquiry ID'}, status=status.HTTP_400_BAD_REQUEST)

    @role_required('admin')
    def handle(req):
        doc = enquiries_col.find_one({'_id': obj_id})
        if not doc:
            return Response({'error': 'Enquiry not found'}, status=status.HTTP_404_NOT_FOUND)

        if req.method == 'GET':
            return Response(serialize_doc(doc), status=status.HTTP_200_OK)

        # PUT
        data = req.data
        update = {}
        for field in ['status', 'notes', 'assigned_to']:
            if field in data:
                update[field] = data[field]
        if not update:
            return Response({'error': 'No fields to update'}, status=status.HTTP_400_BAD_REQUEST)
        update['updated_at'] = datetime.datetime.utcnow()
        enquiries_col.update_one({'_id': obj_id}, {'$set': update})
        return Response({'message': 'Enquiry updated successfully'}, status=status.HTTP_200_OK)

    return handle(request)
