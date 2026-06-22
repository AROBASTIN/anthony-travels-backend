import jwt
import datetime
from django.conf import settings
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password

def generate_tokens(user_id, email, role, name):
    """
    Generate short-lived access_token and long-lived refresh_token.
    """
    now = datetime.datetime.utcnow()
    
    # Access token payload (e.g., 1 hour)
    access_payload = {
        'token_type': 'access',
        'user_id': str(user_id),
        'email': email,
        'role': role,
        'name': name,
        'exp': now + datetime.timedelta(hours=1),
        'iat': now
    }
    
    # Refresh token payload (e.g., 7 days)
    refresh_payload = {
        'token_type': 'refresh',
        'user_id': str(user_id),
        'exp': now + datetime.timedelta(days=7),
        'iat': now
    }
    
    access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')
    
    return access_token, refresh_token

def decode_jwt_token(token):
    """
    Decode and validate a JWT token. Returns decoded dict if valid, otherwise None.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """
    Decorator to ensure a valid JWT token is present in the request's Authorization header.
    """
    @wraps(f)
    def decorator(request, *args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', None)
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            return Response({'error': 'Access Token is missing or invalid'}, status=status.HTTP_401_UNAUTHORIZED)
        
        decoded = decode_jwt_token(token)
        if not decoded:
            return Response({'error': 'Token has expired or is invalid'}, status=status.HTTP_401_UNAUTHORIZED)
            
        if decoded.get('token_type') != 'access':
            return Response({'error': 'Invalid token type. Access token required.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Attach user data to request object
        request.user_id = decoded.get('user_id')
        request.user_email = decoded.get('email')
        request.user_role = decoded.get('role')
        request.user_name = decoded.get('name')
        
        return f(request, *args, **kwargs)
    return decorator

def role_required(allowed_roles):
    """
    Decorator to restrict access to views based on role-based authorization rules.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
        
    def decorator(f):
        @wraps(f)
        @token_required
        def wrapper(request, *args, **kwargs):
            if request.user_role not in allowed_roles:
                return Response({'error': f'Permission denied. Required roles: {allowed_roles}'}, status=status.HTTP_403_FORBIDDEN)
            return f(request, *args, **kwargs)
        return wrapper
    return decorator
