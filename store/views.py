from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, ContactMessage

def populate_dummy_products():
    """
    Auto-populates dummy products if the database is empty.
    This ensures the site has realistic, functional content immediately.
    """
    if Product.objects.count() == 0:
        dummy_data = [
            {
                'name': 'ShopSafe Smart CCTV Camera',
                'description': 'AI-powered, encrypted 4K security camera with real-time motion detection and secure cloud backup.',
                'price': 149.99,
                'category': 'Smart Home Security',
                'stock': 25,
                'image_url': 'https://images.unsplash.com/photo-1557597774-9d273605dfa9?w=400&q=80'
            },
            {
                'name': 'AES-256 Biometric Smart Lock',
                'description': 'Ultra-secure smart lock utilizing military-grade encryption and fingerprint authentication.',
                'price': 199.50,
                'category': 'Smart Home Security',
                'stock': 15,
                'image_url': 'https://images.unsplash.com/photo-1558002038-1055907df827?w=400&q=80'
            },
            {
                'name': 'Secured Firewall Router Pro',
                'description': 'Hardware firewall and gigabit router that filters malicious traffic and blocks cyber threats at the gateway.',
                'price': 299.00,
                'category': 'Network Tech',
                'stock': 10,
                'image_url': 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400&q=80'
            },
            {
                'name': 'Encrypted External SSD (1TB)',
                'description': 'Super-fast external solid-state drive featuring automatic hardware-based encryption and rugged housing.',
                'price': 129.99,
                'category': 'Data Storage',
                'stock': 30,
                'image_url': 'https://images.unsplash.com/photo-1590157121900-575231b53e7f?w=400&q=80'
            },
            {
                'name': 'Privacy Shield Webcam Cover',
                'description': 'Simple, high-quality sliding plastic cover to shield your front-facing laptop and desktop webcams.',
                'price': 9.99,
                'category': 'Accessories',
                'stock': 150,
                'image_url': 'https://images.unsplash.com/photo-1563206767-5b18f218e8de?w=400&q=80'
            },
            {
                'name': 'SafeKey USB Hardware Token',
                'description': 'Two-factor authentication hardware security key to protect logins across major online services.',
                'price': 45.00,
                'category': 'Accessories',
                'stock': 50,
                'image_url': 'https://images.unsplash.com/photo-1618060932014-4beca093fe6f?w=400&q=80'
            }
        ]
        for item in dummy_data:
            Product.objects.create(**item)


def home(request):
    """
    Renders the ShopSafe landing page.
    Automatically ensures products exist and displays the top featured items.
    """
    populate_dummy_products()
    # Get 3 featured products for the hero/frontpage highlight
    featured_products = Product.objects.all().order_by('?')[:3]
    return render(request, 'store/home.html', {'featured_products': featured_products})


def products_list(request):
    """
    Renders the full product catalog.
    Supports filtering by category query parameter.
    """
    populate_dummy_products()
    category = request.GET.get('category', '').strip()
    
    if category:
        products = Product.objects.filter(category__iexact=category)
    else:
        products = Product.objects.all()

    # Get unique categories for side filter
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
    """
    product = get_object_or_404(Product, pk=pk)
    # Get related products in the same category
    related_products = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:3]
    
    context = {
        'product': product,
        'related_products': related_products
    }
    return render(request, 'store/product_detail.html', context)


def about(request):
    """
    Renders the simple static About Us company page.
    """
    return render(request, 'store/about.html')


def contact(request):
    """
    Renders the contact form page.
    Handles message submissions via POST (adds to logs).
    """
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


def search(request):
    """
    Handles site search. Queries database for product names and descriptions.
    Highly vulnerable to search spam / high query frequencies during DDoS.
    """
    populate_dummy_products()
    query = request.GET.get('q', '').strip()
    
    if query:
        from django.db.models import Q
        products = Product.objects.filter(Q(name__icontains=query) | Q(description__icontains=query))
    else:
        products = Product.objects.none()

    context = {
        'products': products,
        'query': query
    }
    return render(request, 'store/search.html', context)
