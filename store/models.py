from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    """
    Model representing products available in the ShopSafe e-commerce store.
    Enhanced to support advanced filtering, brands, ratings, and low-stock thresholds.
    """
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.CharField(max_length=500, blank=True, help_text="Direct link to a product image or placeholder URL")
    category = models.CharField(max_length=100, default='General')
    stock = models.IntegerField(default=10)
    brand = models.CharField(max_length=100, default='ShopSafe')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=4.50)
    low_stock_threshold = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold


class ContactMessage(models.Model):
    """
    Model representing contact form submissions.
    POST requests to the Contact page will write to this table.
    """
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"


class UserProfile(models.Model):
    """
    Links to User model, tracking customer profile statistics and reward points.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    reward_points = models.IntegerField(default=0)

    def __str__(self):
        return f"Profile of {self.user.username}"


class SavedAddress(models.Model):
    """
    Stores billing/shipping addresses for checkout/dashboard management.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=50, default='Home')  # Home, Office, etc.
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} Address for {self.user.username}"


class Wishlist(models.Model):
    """
    Tracks saved customer items.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} saved {self.product.name}"


class BrowsingHistory(models.Model):
    """
    Logs recently viewed items by customers to feed the recommendation engine.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='browsing_history')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} viewed {self.product.name}"


class Order(models.Model):
    """
    Manages complete checkout logs.
    """
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('packing', 'Packing'),
        ('shipping', 'Shipping'),
        ('delivered', 'Delivered'),
        ('stopped', 'Cancelled'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_id = models.CharField(max_length=50, unique=True)
    shipping_address = models.TextField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    payment_status = models.CharField(max_length=20, default='paid')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_id}"


class OrderStatusHistory(models.Model):
    """
    Logs status transition history for tracking portal.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20)
    updated_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.order.order_id} status to {self.status}"


class OrderItem(models.Model):
    """
    Details items contained in an order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} inside {self.order.order_id}"


class FlashSale(models.Model):
    """
    Dynamic flash promotional parameters.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='flash_sales')
    discount_price = models.DecimalField(max_digits=10, decimal_places=2)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    flash_stock = models.IntegerField(default=10)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Flash sale on {self.product.name}"


class Coupon(models.Model):
    """
    Models active promo discount codes.
    """
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, default='percentage')  # percentage, flat
    value = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Notification(models.Model):
    """
    Inbox model for customer updates and notifications.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"
