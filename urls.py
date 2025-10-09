from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('panel/', include('mi_finanzas.urls')),
    path('', RedirectView.as_view(url='panel/', permanent=True)),
]
