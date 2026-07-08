import datetime
import random
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from store.models import Product, Coupon, FlashSale, Order, OrderItem, OrderStatusHistory, UserProfile, SavedAddress, Wishlist

def run_fixtures():
    """
    Populates all necessary database tables with high-fidelity dummy data
    for products, coupons, flash sales, and historical orders.
    """
    now = timezone.now()

    # ── 1. Populate Products ───────────────────────────────────────────────
    if Product.objects.count() == 0:
        dummy_products = [
            {
                'name': 'ShopSafe Smart CCTV Camera',
                'description': 'AI-powered, encrypted 4K security camera with real-time motion detection and secure cloud backup.',
                'price': 149.99,
                'category': 'Smart Home Security',
                'stock': 25,
                'brand': 'Ring',
                'rating': 4.80,
                'low_stock_threshold': 5,
                'image_url': 'https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=400&q=80'
            },
            {
                'name': 'AES-256 Biometric Smart Lock',
                'description': 'Ultra-secure smart lock utilizing military-grade encryption and fingerprint authentication.',
                'price': 199.50,
                'category': 'Smart Home Security',
                'stock': 15,
                'brand': 'Schlage',
                'rating': 4.70,
                'low_stock_threshold': 3,
                'image_url': 'https://images.unsplash.com/photo-1558002038-1055907df827?w=400&q=80'
            },
            {
                'name': 'Secured Firewall Router Pro',
                'description': 'Hardware firewall and gigabit router that filters malicious traffic and blocks cyber threats at the gateway.',
                'price': 299.00,
                'category': 'Network Tech',
                'stock': 2,  # Low stock warning will trigger immediately
                'brand': 'Cisco',
                'rating': 4.90,
                'low_stock_threshold': 3,
                'image_url': 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400&q=80'
            },
            {
                'name': 'Encrypted External SSD (1TB)',
                'description': 'Super-fast external solid-state drive featuring automatic hardware-based encryption and rugged housing.',
                'price': 129.99,
                'category': 'Data Storage',
                'brand': 'Samsung',
                'rating': 4.60,
                'low_stock_threshold': 5,
                'stock': 30,
                'image_url': 'https://images.unsplash.com/photo-1590157121900-575231b53e7f?w=400&q=80'
            },
            {
                'name': 'Privacy Shield Webcam Cover',
                'description': 'Simple, high-quality sliding plastic cover to shield your front-facing laptop and desktop webcams.',
                'price': 9.99,
                'category': 'Accessories',
                'brand': 'Logitech',
                'rating': 4.20,
                'low_stock_threshold': 20,
                'stock': 150,
                'image_url': 'https://images.unsplash.com/photo-1563206767-5b18f218e8de?w=400&q=80'
            },
            {
                'name': 'SafeKey USB Hardware Token',
                'description': 'Two-factor authentication hardware security key to protect logins across major online services.',
                'price': 45.00,
                'category': 'Accessories',
                'brand': 'Yubico',
                'rating': 4.95,
                'low_stock_threshold': 10,
                'stock': 50,
                'image_url': 'https://images.unsplash.com/photo-1618060932014-4beca093fe6f?w=400&q=80'
            }
        ]
        for item in dummy_products:
            Product.objects.create(**item)

    # ── 2. Populate Coupons ────────────────────────────────────────────────
    if Coupon.objects.count() == 0:
        coupons = [
            {'code': 'SAVE10', 'discount_type': 'percentage', 'value': 10.00},
            {'code': 'WELCOME5', 'discount_type': 'flat', 'value': 5.00},
            {'code': 'CYBER50', 'discount_type': 'percentage', 'value': 50.00},
        ]
        for c in coupons:
            Coupon.objects.create(**c)

    # ── 3. Populate Flash Sales ────────────────────────────────────────────
    if FlashSale.objects.count() == 0:
        smart_lock = Product.objects.filter(name__icontains='Smart Lock').first()
        safekey = Product.objects.filter(name__icontains='SafeKey').first()

        if smart_lock:
            FlashSale.objects.create(
                product=smart_lock,
                discount_price=149.00,
                start_time=now - datetime.timedelta(hours=12),
                end_time=now + datetime.timedelta(hours=36),
                flash_stock=4,
                active=True
            )
        if safekey:
            FlashSale.objects.create(
                product=safekey,
                discount_price=29.99,
                start_time=now - datetime.timedelta(hours=6),
                end_time=now + datetime.timedelta(hours=18),
                flash_stock=8,
                active=True
            )

    # ── 4. Populate Users and Profiles ─────────────────────────────────────
    # Make sure all existing users have UserProfile and SavedAddress entries
    for user in User.objects.all():
        UserProfile.objects.get_or_create(user=user, defaults={'reward_points': random.randint(100, 800)})
        SavedAddress.objects.get_or_create(
            user=user,
            label='Home',
            defaults={
                'street': '1024 Cryptography Blvd',
                'city': 'Secured City',
                'state': 'Metro Cyber',
                'postal_code': '40300'
            }
        )

    # Create dummy users for analytics if count is very low (e.g. only admin)
    if User.objects.count() <= 1:
        dummy_users = [
            ('analyst', 'analyst@shopsafe.local', 'security'),
            ('johndoe', 'john@gmail.com', 'securepass123'),
            ('janedoe', 'jane@yahoo.com', 'mypass987'),
            ('cybergeek', 'geek@github.com', 'cyberpass77'),
        ]
        for username, email, pwd in dummy_users:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(username=username, email=email, password=pwd)
                UserProfile.objects.create(user=u, reward_points=random.randint(150, 750))
                SavedAddress.objects.create(
                    user=u,
                    label='Home',
                    street=f"{random.randint(10, 999)} Security Rd",
                    city='Packet Loss City',
                    state='Laguna',
                    postal_code='4027'
                )

    # ── 5. Populate Historical Orders (for Sales Analytics Graphs) ──────────
    if Order.objects.count() == 0:
        users = list(User.objects.all())
        products = list(Product.objects.all())
        statuses = ['processing', 'packing', 'shipping', 'delivered']

        # Pre-generate 12 orders spanning the last 7 days
        for i in range(1, 13):
            user = random.choice(users)
            order_date = now - datetime.timedelta(days=random.randint(0, 6), hours=random.randint(1, 23))
            
            # Select 1-2 random products
            order_products = random.sample(products, k=random.randint(1, 2))
            total_amount = Decimal('0.00')
            items_to_create = []

            for p in order_products:
                qty = random.randint(1, 2)
                price = p.price
                total_amount += price * qty
                items_to_create.append((p, price, qty))

            tax = total_amount * Decimal('0.10')
            shipping = Decimal('0.00') if total_amount > Decimal('100.00') else Decimal('5.00')
            final_total = total_amount + tax + shipping

            status = random.choice(statuses) if order_date.date() < now.date() else 'processing'

            order = Order.objects.create(
                user=user,
                order_id=f"ORD-{order_date.strftime('%Y%m%d%H%M')}-{random.randint(100, 999)}",
                shipping_address=f"{user.addresses.first().street}, {user.addresses.first().city}, {user.addresses.first().state} {user.addresses.first().postal_code}",
                total_amount=final_total,
                tax_amount=tax,
                shipping_cost=shipping,
                discount_amount=0.00,
                status=status,
                payment_status='paid'
            )
            # Hack django auto_now_add to preserve historical timestamps
            Order.objects.filter(pk=order.pk).update(created_at=order_date)

            for p, price, qty in items_to_create:
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    price=price,
                    quantity=qty
                )

            # Generate Status history transition timeline
            # E.g. if status is delivered, we log history for processing -> packing -> shipping -> delivered
            stages = ['processing', 'packing', 'shipping', 'delivered']
            current_stage_idx = stages.index(status)
            
            for stage_idx in range(current_stage_idx + 1):
                stage_status = stages[stage_idx]
                stage_date = order_date + datetime.timedelta(hours=stage_idx * 4)
                hist = OrderStatusHistory.objects.create(
                    order=order,
                    status=stage_status,
                    notes=f"Order transitioned to {stage_status} stage."
                )
                OrderStatusHistory.objects.filter(pk=hist.pk).update(updated_at=stage_date)
                
            # Create a wishlist entry for this user
            Wishlist.objects.get_or_create(user=user, product=random.choice(products))
