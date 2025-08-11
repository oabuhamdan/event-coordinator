from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, OrganizationRegistrationForm

def register_user(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register_user.html', {'form': form})

def register_organization(request):
    if request.method == 'POST':
        form = OrganizationRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Organization registration successful!')
            return redirect('organizations:create_profile')
    else:
        form = OrganizationRegistrationForm()
    return render(request, 'registration/register_organization.html', {'form': form})

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')