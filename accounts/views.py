from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

def login_view(request):
    """
    Renders login form and processes authentication.
    Failed logins generate POST requests that are forwarded to NetWatch,
    which is excellent for verifying login attempt rate limits.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}! You have successfully logged in.")
                return redirect('home')
        else:
            messages.error(request, "⚠ Invalid username or password. Please try again.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    """
    Renders and processes user registration.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in immediately after registering
            login(request, user)
            messages.success(request, "✓ Registration successful! Welcome to ShopSafe.")
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"⚠ {error}")
    else:
        form = UserCreationForm()
        
    return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    """
    Logs the user out of the application session.
    """
    logout(request)
    messages.info(request, "You have been logged out of your session.")
    return redirect('home')


@login_required
def profile_view(request):
    """
    Renders the authenticated user profile dashboard view.
    """
    return render(request, 'accounts/profile.html')
