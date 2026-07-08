import random
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Product, ContactMessage, UserProfile, SavedAddress, Wishlist, BrowsingHistory, Order, OrderStatusHistory, OrderItem, FlashSale, Coupon, Notification

def populate_dummy_products():
    """
    Auto-populates dummy products and historical order logs via the fixtures helper.
    """
    from .populate_fixtures import run_fixtures
    run_fixtures()


# ─── Core Pages ────────────────────────────────────────────────────────────

def get_recommendations(user):
    """
    Recommendation helper logic based on user's category browsing history.
    """
    if user and user.is_authenticated:
        # Fetch viewed categories from browsing history
        viewed_categories = BrowsingHistory.objects.filter(user=user).values_list('product__category', flat=True).distinct()
        if viewed_categories:
            return Product.objects.filter(category__in=viewed_categories).exclude(
                browsing_history__user=user
            ).distinct().order_by('?')[:6]
    # Fallback recommendations using highest rated items
    return Product.objects.all().order_by('-rating')[:6]


def home(request):
    """
    Renders the ShopSafe landing page.
    """
    populate_dummy_products()
    now = timezone.now()
    
    # Active flash sales countdown highlight
    flash_sales = FlashSale.objects.filter(active=True, start_time__lte=now, end_time__gte=now).select_related('product')
    featured_products = Product.objects.all().order_by('?')[:3]
    recommendations = get_recommendations(request.user)

    context = {
        'featured_products': featured_products,
        'flash_sales': flash_sales,
        'recommendations': recommendations[:3],
    }
    return render(request, 'store/home.html', context)


def products_list(request):
    """
    Renders the full product catalog.
    """
    populate_dummy_products()
    category = request.GET.get('category', '').strip()
    
    if category:
        products = Product.objects.filter(category__iexact=category)
    else:
        products = Product.objects.all()

    categories = Product.objects.values_list('category', flat=True).distinct()

    context = {
        'products': products,
        'categories': categories,
        'selected_category': category
    }
    return render(request, 'store/products.html', context)


def product_detail(request, pk):
    """
    Renders the detail page for a single product.
    Automatically logs browsing history details for recommendation telemetry.
    """
    populate_dummy_products()
    product = get_object_or_404(Product, pk=pk)
    
    # Track browsing history for personalization
    if request.user.is_authenticated:
        BrowsingHistory.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={'viewed_at': timezone.now()}
        )
    
    related_products = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:3]
    frequently_bought = Product.objects.exclude(pk=product.pk).order_by('?')[:2]
    
    # Dynamic Flash Sale pricing integration
    now = timezone.now()
    flash_sale = FlashSale.objects.filter(product=product, active=True, start_time__lte=now, end_time__gte=now).first()
    display_price = flash_sale.discount_price if flash_sale else product.price

    context = {
        'product': product,
        'related_products': related_products,
        'frequently_bought': frequently_bought,
        'flash_sale': flash_sale,
        'display_price': display_price,
    }
    return render(request, 'store/product_detail.html', context)


def about(request):
    return render(request, 'store/about.html')


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and subject and message:
            ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message
            )
            messages.success(request, "✓ Thank you! Your message has been sent. Our team will contact you shortly.")
            return redirect('contact')
        else:
            messages.error(request, "⚠ Please fill in all fields before submitting.")

    return render(request, 'store/contact.html')


# ─── Advanced Search ───────────────────────────────────────────────────────

def search(request):
    """
    Handles advanced search queries with sorting, pricing filters, and brand tags.
    """
    populate_dummy_products()
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    brand = request.GET.get('brand', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    min_rating = request.GET.get('min_rating', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()

    products = Product.objects.all()

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category:
        products = products.filter(category__iexact=category)
    if brand:
        products = products.filter(brand__iexact=brand)
    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except ValueError:
            pass
    if min_rating:
        try:
            products = products.filter(rating__gte=Decimal(min_rating))
        except ValueError:
            pass

    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'rating':
        products = products.order_by('-rating')
    else:
        products = products.order_by('-created_at')

    categories = Product.objects.values_list('category', flat=True).distinct()
    brands = Product.objects.values_list('brand', flat=True).distinct()

    # Paginate results
    paginator = Paginator(products, 4)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'categories': categories,
        'brands': brands,
        'selected_category': category,
        'selected_brand': brand,
        'min_price': min_price,
        'max_price': max_price,
        'min_rating': min_rating,
        'sort_by': sort_by,
    }
    return render(request, 'store/search.html', context)


def search_suggest(request):
    """
    Search suggestion endpoint returning autocomplete JSON objects.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    products = Product.objects.filter(Q(name__icontains=query) | Q(description__icontains=query))[:5]
    suggestions = [{'id': p.id, 'name': p.name, 'price': str(p.price)} for p in products]
    return JsonResponse({'suggestions': suggestions})


# ─── Checkout and Flash Sales ──────────────────────────────────────────────

def flash_sales_list(request):
    populate_dummy_products()
    now = timezone.now()
    flash_sales = FlashSale.objects.filter(active=True, start_time__lte=now, end_time__gte=now).select_related('product')
    return render(request, 'store/flash_sales.html', {'flash_sales': flash_sales})


def checkout_view(request):
    """
    Checkout simulation view. Calculates taxes (10%), dynamic shipping,
    coupon validations, and handles checkout stock updates.
    """
    populate_dummy_products()
    
    product_id = request.GET.get('product_id')
    quantity = int(request.GET.get('qty', 1))
    
    cart_items = []
    subtotal = Decimal('0.00')

    coupon_code = request.session.get('applied_coupon')
    coupon = None
    discount = Decimal('0.00')
    
    if coupon_code:
        coupon = Coupon.objects.filter(code__iexact=coupon_code, active=True).first()

    if product_id:
        product = get_object_or_404(Product, pk=product_id)
        now = timezone.now()
        flash_sale = FlashSale.objects.filter(product=product, active=True, start_time__lte=now, end_time__gte=now).first()
        price = flash_sale.discount_price if flash_sale else product.price
        item_total = price * quantity
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'price': price,
            'total': item_total
        })
        subtotal += item_total
    else:
        # Fetch from session cart
        cart = request.session.get('cart', {})
        if not cart:
            cctv = Product.objects.first()
            if cctv:
                cart = {str(cctv.id): 1}
                request.session['cart'] = cart

        for pid, qty in cart.items():
            product = Product.objects.filter(pk=int(pid)).first()
            if product:
                now = timezone.now()
                flash_sale = FlashSale.objects.filter(product=product, active=True, start_time__lte=now, end_time__gte=now).first()
                price = flash_sale.discount_price if flash_sale else product.price
                item_total = price * qty
                cart_items.append({
                    'product': product,
                    'quantity': qty,
                    'price': price,
                    'total': item_total
                })
                subtotal += item_total

    if coupon:
        if coupon.discount_type == 'percentage':
            discount = subtotal * (coupon.value / Decimal('100.00'))
        else:
            discount = coupon.value
            if discount > subtotal:
                discount = subtotal

    tax = (subtotal - discount) * Decimal('0.10')
    shipping = Decimal('0.00') if subtotal > Decimal('100.00') else Decimal('5.00')
    total = subtotal - discount + tax + shipping

    if request.method == 'POST':
        shipping_address = request.POST.get('shipping_address', '').strip()
        card_name = request.POST.get('card_name', '').strip()
        card_number = request.POST.get('card_number', '').strip()
        
        if not shipping_address or not card_name or not card_number:
            messages.error(request, "⚠ Please fill in all billing and shipping information.")
            return redirect(f"{request.path}?product_id={product_id or ''}&qty={quantity}")

        # Check stock limits
        for item in cart_items:
            product = item['product']
            req_qty = item['quantity']
            if product.stock < req_qty:
                messages.error(request, f"⚠ Error: Insufficient stock for {product.name}. Only {product.stock} left.")
                return redirect(f"{request.path}?product_id={product_id or ''}&qty={quantity}")

        # Finalize order and update database tables
        order_id = f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            order_id=order_id,
            shipping_address=shipping_address,
            total_amount=total,
            tax_amount=tax,
            shipping_cost=shipping,
            discount_amount=discount,
            status='processing',
            payment_status='paid'
        )

        OrderStatusHistory.objects.create(
            order=order,
            status='processing',
            notes="Order placed. Payment processor simulation validated."
        )

        for item in cart_items:
            product = item['product']
            req_qty = item['quantity']
            
            product.stock = max(0, product.stock - req_qty)
            product.save()

            OrderItem.objects.create(
                order=order,
                product=product,
                price=item['price'],
                quantity=req_qty
            )

            # Generate admin notifications on low stock warnings
            if product.is_low_stock:
                for staff_user in User.objects.filter(is_staff=True):
                    Notification.objects.create(
                        user=staff_user,
                        title=f"Low Stock Alert: {product.name}",
                        message=f"Stock limit warning reached for {product.name} (Current Stock: {product.stock})."
                    )

        # Clear checkout session parameters
        request.session['applied_coupon'] = None
        if 'cart' in request.session:
            request.session['cart'] = {}

        if request.user.is_authenticated:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            earned_points = int(total / Decimal('10.00'))
            profile.reward_points += earned_points
            profile.save()
            
            Notification.objects.create(
                user=request.user,
                title="Order Received",
                message=f"Order {order_id} has been recorded. Added {earned_points} rewards."
            )

        messages.success(request, f"✓ Purchase Successful! Order ID: {order_id}")
        return redirect('order_tracking')

    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'discount': discount,
        'coupon': coupon,
        'tax': tax,
        'shipping': shipping,
        'total': total,
        'product_id': product_id,
        'quantity': quantity
    }
    return render(request, 'store/checkout.html', context)


def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip().upper()
        product_id = request.POST.get('product_id', '')
        qty = request.POST.get('qty', '1')
        
        coupon = Coupon.objects.filter(code=code, active=True).first()
        if coupon:
            request.session['applied_coupon'] = code
            messages.success(request, f"✓ Coupon code applied!")
        else:
            messages.error(request, "⚠ Invalid coupon code.")
        
        return redirect(f"/checkout/?product_id={product_id}&qty={qty}")
    return redirect('products')


# ─── Live Order Tracking ──────────────────────────────────────────────────

def order_tracking_view(request):
    """
    Renders status timeline logs for a given order id lookup.
    """
    populate_dummy_products()
    order_id = request.GET.get('order_id', '').strip()
    order = None
    history = []

    if order_id:
        order = Order.objects.filter(order_id__iexact=order_id).prefetch_related('status_history', 'items__product').first()
        if order:
            history = order.status_history.all().order_by('updated_at')
        else:
            messages.error(request, f"⚠ Order '{order_id}' not found.")

    return render(request, 'store/tracking.html', {'order': order, 'history': history, 'order_id': order_id})


# ─── Customer Dashboard ───────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    """
    Renders customer portal stats, addresses, wishlist, and notification logs.
    """
    populate_dummy_products()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    addresses = SavedAddress.objects.filter(user=request.user)
    wishlist = Wishlist.objects.filter(user=request.user).select_related('product')
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created_at')
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    recently_viewed = BrowsingHistory.objects.filter(user=request.user).select_related('product').order_by('-viewed_at')[:4]
    coupons = Coupon.objects.filter(active=True)

    context = {
        'profile': profile,
        'addresses': addresses,
        'wishlist': wishlist,
        'orders': orders,
        'notifications': notifications,
        'recently_viewed': recently_viewed,
        'coupons': coupons
    }
    return render(request, 'store/dashboard.html', context)


@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
    if wishlist_item:
        wishlist_item.delete()
        messages.success(request, f"Removed {product.name} from wishlist.")
    else:
        Wishlist.objects.create(user=request.user, product=product)
        messages.success(request, f"Added {product.name} to wishlist.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required
def add_address(request):
    if request.method == 'POST':
        label = request.POST.get('label', 'Home').strip()
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        
        if street and city and state and postal_code:
            SavedAddress.objects.create(
                user=request.user,
                label=label,
                street=street,
                city=city,
                state=state,
                postal_code=postal_code
            )
            messages.success(request, "✓ Address added.")
        else:
            messages.error(request, "⚠ Fill all address fields.")
    return redirect('dashboard')


@login_required
def delete_address(request, pk):
    address = get_object_or_404(SavedAddress, pk=pk, user=request.user)
    address.delete()
    messages.success(request, "Address deleted.")
    return redirect('dashboard')


@login_required
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    messages.success(request, "All notifications read.")
    return redirect('dashboard')


# ─── Sales Analytics (Administrator) ───────────────────────────────────────

@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def admin_dashboard_view(request):
    """
    Administrative overview rendering product, sales, and total customer charts.
    """
    populate_dummy_products()
    
    total_revenue = Order.objects.filter(payment_status='paid').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_orders = Order.objects.count()
    total_customers = User.objects.count()
    
    low_stock_products = Product.objects.filter(stock__lte=F('low_stock_threshold'))
    
    best_sellers = OrderItem.objects.values('product__name', 'product__price').annotate(
        total_sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'))
    ).order_by('-total_sold')[:5]
    
    # Query last 7 days daily sales
    daily_sales = Order.objects.extra(select={'day': "date(created_at)"}).values('day').annotate(
        revenue=Sum('total_amount'),
        orders_count=Count('id')
    ).order_by('day')[-7:]

    # Serialize Decimal/Date types to clean JSON formats for Javascript Charts
    daily_sales_list = []
    for s in daily_sales:
        daily_sales_list.append({
            'day': str(s['day']),
            'revenue': float(s['revenue'] or 0),
            'orders_count': int(s['orders_count'] or 0)
        })
    daily_sales_json = json.dumps(daily_sales_list)

    pending_orders = Order.objects.filter(status__in=['processing', 'packing', 'shipping']).order_by('-created_at')[:10]

    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_customers': total_customers,
        'low_stock_products': low_stock_products,
        'best_sellers': best_sellers,
        'daily_sales_json': daily_sales_json,
        'pending_orders': pending_orders,
    }
    return render(request, 'store/admin_dashboard.html', context)


# ─── REST Business API Endpoints ──────────────────────────────────────────

def api_products_search(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    
    products = Product.objects.all()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category:
        products = products.filter(category__iexact=category)
        
    paginator = Paginator(products, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    data = {
        'count': paginator.count,
        'num_pages': paginator.num_pages,
        'current_page': page_obj.number,
        'results': [{
            'id': p.id,
            'name': p.name,
            'brand': p.brand,
            'price': str(p.price),
            'rating': str(p.rating),
            'stock': p.stock
        } for p in page_obj]
    }
    return JsonResponse(data)


def api_products_inventory(request):
    product_id = request.GET.get('id')
    if not product_id:
        return JsonResponse({'error': 'Product id parameter is required.'}, status=400)
    product = Product.objects.filter(pk=int(product_id)).first()
    if not product:
        return JsonResponse({'error': 'Product not found.'}, status=404)
    return JsonResponse({
        'id': product.id,
        'name': product.name,
        'stock': product.stock,
        'is_low_stock': product.is_low_stock
    })


def api_orders_status(request):
    order_id = request.GET.get('order_id')
    if not order_id:
        return JsonResponse({'error': 'Order id parameter is required.'}, status=400)
    order = Order.objects.filter(order_id__iexact=order_id).prefetch_related('status_history').first()
    if not order:
        return JsonResponse({'error': 'Order not found.'}, status=404)
    
    history = [{
        'status': h.status,
        'timestamp': h.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        'notes': h.notes
    } for h in order.status_history.all().order_by('updated_at')]
    
    return JsonResponse({
        'order_id': order.order_id,
        'current_status': order.status,
        'history': history
    })


def api_products_recommendations(request):
    user_id = request.GET.get('user_id')
    user = User.objects.filter(pk=user_id).first() if user_id else None
    recs = get_recommendations(user)
    return JsonResponse({
        'results': [{
            'id': p.id,
            'name': p.name,
            'price': str(p.price),
            'rating': str(p.rating),
            'brand': p.brand
        } for p in recs]
    })


def api_customer_profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    notifications = Notification.objects.filter(user=request.user, read=False)[:5]
    
    return JsonResponse({
        'username': request.user.username,
        'email': request.user.email,
        'reward_points': profile.reward_points,
        'unread_notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'timestamp': n.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for n in notifications]
    })


def api_dashboard_stats(request):
    return JsonResponse({
        'total_products': Product.objects.count(),
        'total_orders': Order.objects.count(),
        'total_active_flash_sales': FlashSale.objects.filter(active=True).count(),
        'total_coupons': Coupon.objects.filter(active=True).count()
    })
