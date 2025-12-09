from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# Force redirect home page to login
def force_login(request):
    return redirect("login")

# Import OTP views (safe to import here)
from welcome.views import login_page, verify_otp

urlpatterns = [
    path('admin/', admin.site.urls),

    # Redirect base URL to login
    path('', force_login, name="force_login"),

    # App URLs
    path('ballot/', include('ballot.urls')),
    path('sim/', include('simulation.urls')),
    path('welcome/', include('welcome.urls')),

    # OTP authentication URLs
    path('login/', login_page, name="login"),
    path('verify/', verify_otp, name="verify_otp"),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
