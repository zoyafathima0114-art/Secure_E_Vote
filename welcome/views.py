from django.conf import settings
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.mail import send_mail
from django.contrib import messages
import random

def home(request):
    context = {
        'tx': settings.N_TRANSACTIONS,
        'bl': settings.N_BLOCKS,
    }
    return render(request, 'welcome/home.html', context)

def login_page(request):
    if request.method == "POST":
        email = request.POST.get("email")
        otp = random.randint(100000, 999999)

        request.session["otp"] = otp
        request.session["email"] = email

        send_mail(
            subject="Your Login Verification Code",
            message=f"Your OTP is {otp}",
            from_email="zoyafathima0114@gmail.com",
            recipient_list=[email],
        )

        return redirect("verify_otp")

    return render(request, "login.html")

def verify_otp(request):
    if request.method == "POST":
        user_otp = request.POST.get("otp")
        session_otp = request.session.get("otp")

        if not user_otp:
            messages.error(request, "OTP cannot be empty!")
            return redirect("verify_otp")

        if not session_otp:
            messages.error(request, "Session expired. Please login again.")
            return redirect("login")

        if str(user_otp).strip() == str(session_otp).strip():
            messages.success(request, "Login Success!")
            return redirect("welcome:home")

        messages.error(request, "Invalid OTP!")
        return redirect("verify_otp")

    return render(request, "verify_otp.html")
