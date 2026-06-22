import os
import django
import datetime
from pathlib import Path

# Load .env before Django settings initialise
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / '.env')

# Setup Django context to allow usage of settings and hashing utilities
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_backend.settings')
django.setup()

from django.contrib.auth.hashers import make_password
from api.db import (
    users_col, drivers_col, vehicles_col, reviews_col, faqs_col, fuel_prices_col, bookings_col, payments_col,
    pricing_config_col, website_content_col
)

def seed():
    print("Clearing existing database collections...")
    users_col.delete_many({})
    drivers_col.delete_many({})
    vehicles_col.delete_many({})
    reviews_col.delete_many({})
    faqs_col.delete_many({})
    fuel_prices_col.delete_many({})
    bookings_col.delete_many({})
    payments_col.delete_many({})
    pricing_config_col.delete_many({})
    website_content_col.delete_many({})

    print("Seeding Default Accounts...")
    hashed_pwd = make_password("password123")
    
    # 1. Customer
    customer = {
        "name": "Arjun Kumar",
        "email": "customer@travels.com",
        "password": hashed_pwd,
        "role": "customer",
        "phone": "+91 9876543210",
        "status": "active",
        "created_at": datetime.datetime.utcnow()
    }
    cust_id = users_col.insert_one(customer).inserted_id
    print(f"Seeded Customer: {customer['email']}")

    # 2. Driver
    driver = {
        "name": "Rajesh Shinde",
        "email": "driver@travels.com",
        "password": hashed_pwd,
        "role": "driver",
        "phone": "+91 8888888888",
        "status": "active",
        "created_at": datetime.datetime.utcnow()
    }
    drvr_id = users_col.insert_one(driver).inserted_id
    
    # Driver details doc
    driver_detail = {
        "user_id": str(drvr_id),
        "name": "Rajesh Shinde",
        "experience": 9,
        "languages": ["Hindi", "English", "Marathi"],
        "rating": 4.95,
        "status": "available",
        "verified": True,
        "documents": {
            "license": {"status": "verified", "file": "license.pdf"},
            "aadhar": {"status": "verified", "file": "aadhar.pdf"}
        }
    }
    drivers_col.insert_one(driver_detail)
    print(f"Seeded Driver: {driver['email']}")

    # 3. Cab Owner
    owner = {
        "name": "Anthony Gonsalves",
        "email": "owner@travels.com",
        "password": hashed_pwd,
        "role": "cab_owner",
        "phone": "+91 7777777777",
        "status": "active",
        "created_at": datetime.datetime.utcnow()
    }
    owner_id = users_col.insert_one(owner).inserted_id
    print(f"Seeded Cab Owner: {owner['email']}")

    # 4. Admin
    admin = {
        "name": "Super Admin",
        "email": "admin@travels.com",
        "password": hashed_pwd,
        "role": "admin",
        "phone": "+91 9999999999",
        "status": "active",
        "created_at": datetime.datetime.utcnow()
    }
    users_col.insert_one(admin)
    print(f"Seeded Admin: {admin['email']}")

    print("Seeding Vehicles...")
    vehicles = [
        {
            "name": "Maruti Suzuki WagonR",
            "category": "hatchback",
            "plate_number": "MH-12-PQ-1234",
            "seats": 4,
            "price_per_km": 12,
            "fuel": "CNG/Petrol",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.8,
            "reviews": 120,
            "approved": True
        },
        {
            "name": "Maruti Suzuki Dzire",
            "category": "sedan",
            "plate_number": "MH-12-RS-5678",
            "seats": 4,
            "price_per_km": 14,
            "fuel": "Petrol/Diesel",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.9,
            "reviews": 210,
            "approved": True
        },
        {
            "name": "Maruti Suzuki Ertiga",
            "category": "suv",
            "plate_number": "MH-12-TU-9012",
            "seats": 6,
            "price_per_km": 16,
            "fuel": "CNG/Diesel",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.85,
            "reviews": 195,
            "approved": True
        },
        {
            "name": "Toyota Innova Crysta",
            "category": "crysta",
            "plate_number": "MH-12-VW-3456",
            "seats": 7,
            "price_per_km": 22,
            "fuel": "Diesel",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.96,
            "reviews": 450,
            "approved": True
        },
        {
            "name": "Force Tempo Traveller",
            "category": "traveller",
            "plate_number": "MH-12-XY-7890",
            "seats": 14,
            "price_per_km": 26,
            "fuel": "Diesel",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.9,
            "reviews": 85,
            "approved": True
        },
        {
            "name": "Tata Ultra Mini Bus",
            "category": "minibus",
            "plate_number": "MH-12-ZA-2345",
            "seats": 25,
            "price_per_km": 35,
            "fuel": "Diesel",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.8,
            "reviews": 42,
            "approved": True
        },
        {
            "name": "Mercedes-Benz E-Class",
            "category": "luxury",
            "plate_number": "MH-12-BC-6789",
            "seats": 4,
            "price_per_km": 50,
            "fuel": "Petrol",
            "ac": True,
            "driver_available": True,
            "owner_id": str(owner_id),
            "status": "available",
            "rating": 4.98,
            "reviews": 64,
            "approved": True
        }
    ]
    vehicles_col.insert_many(vehicles)
    print(f"Seeded {len(vehicles)} vehicles.")

    print("Seeding Fuel Prices...")
    fuel_prices_col.insert_one({
        "petrol": 103.44,
        "diesel": 89.79,
        "updated_at": datetime.datetime.utcnow()
    })
    print("Seeded fuel prices.")

    print("Seeding FAQs...")
    faqs = [
        {"question": "How are outstation fares calculated?", "answer": "Fares include vehicle rent (per day/km), driver salary, distance fuel charge, tolls, platform fee, and 5% GST for maximum transparency."},
        {"question": "Can I request a trip without a driver?", "answer": "Yes! You can uncheck 'Driver Required' in the booking form to opt for self-drive rentals on available models."},
        {"question": "What is the cancellation policy?", "answer": "Cancellations made 6 hours prior to the trip pickup time are 100% free. Inside 6 hours, a standard platform cancellation fee of ₹150 applies."},
        {"question": "Are the cars clean and sanitized?", "answer": "Absolutely! We enforce strict safety and hygiene standards. Every car is deep sanitized after each trip, and drivers are fully verified."}
    ]
    faqs_col.insert_many(faqs)
    print(f"Seeded {len(faqs)} FAQs.")

    print("Seeding Customer Reviews...")
    reviews = [
        {"customer_name": "Rohan Deshmukh", "rating": 5, "comment": "Extremely premium service! The Innova Crysta was neat and clean. Rajesh was a very professional and polite driver.", "created_at": datetime.datetime.utcnow()},
        {"customer_name": "Siddharth Mehta", "rating": 5, "comment": "The fare transparency is the best part of Anthony Travels. What you see is exactly what you pay. Strongly recommended!", "created_at": datetime.datetime.utcnow()},
        {"customer_name": "Priya Sharma", "rating": 4, "comment": "Excellent experience with the Sedan booking. Easy login, and instantaneous WhatsApp updates. Will book again.", "created_at": datetime.datetime.utcnow()}
    ]
    reviews_col.insert_many(reviews)
    print(f"Seeded {len(reviews)} reviews.")

    print("Seeding Pricing Config...")
    pricing_config = {
        "base_rent": {
            "hatchback": 1200,
            "sedan": 1600,
            "suv": 2200,
            "crysta": 3200,
            "traveller": 4500,
            "minibus": 6500,
            "luxury": 10000
        },
        "km_rates": {
            "hatchback": 12,
            "sedan": 14,
            "suv": 16,
            "crysta": 22,
            "traveller": 26,
            "minibus": 35,
            "luxury": 50
        },
        "driver_salary": 400,
        "platform_fee": 99,
        "gst_percent": 5,
        "offers_enabled": True
    }
    pricing_config_col.insert_one(pricing_config)
    print("Seeded global pricing configuration.")

    print("Seeding Homepage/Website Content Config...")
    website_content = {
        "hero_title": "Premium Outstation & Local Cab Service",
        "hero_subtitle": "Anthony Travels provides transparent pricing, verified professional drivers, and top-tier cars for a premium travel experience across India.",
        "company_info": "Anthony Travels is a premier travel booking service designed for Indian customers, offering car rentals, outstation trips, airport transfers, and corporate travel.",
        "contact_phone": "+91 99999 88888",
        "contact_email": "bookings@anthonytravels.com",
        "contact_address": "Anthony Travels HQ, Suite 404, Cyber City, Gurugram, India",
        "last_updated": datetime.datetime.utcnow()
    }
    website_content_col.insert_one(website_content)
    print("Seeded website content config.")

    print("\nDatabase seeded successfully!")

if __name__ == '__main__':
    seed()
