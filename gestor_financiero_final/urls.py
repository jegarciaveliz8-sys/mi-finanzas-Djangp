from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import urls as auth_urls 
# Asegúrate de que esta línea es correcta para tu proyecto
from mi_finanzas.views import RegistroUsuarioView 

urlpatterns = [
    # Ruta de Administración
    path('admin/', admin.site.urls),

    # 1. Rutas de Autenticación de Django (login, logout, etc.)
    # Define los patrones 'auth:login', 'auth:logout', etc.
    path('accounts/', include((auth_urls, 'auth'), namespace='auth')), 

    # 2. Rutas de Registro (CRÍTICO: Define el patrón 'signup')
    # Esta línea resuelve el error NoReverseMatch que viste.
    path('accounts/signup/', RegistroUsuarioView.as_view(), name='signup'), 

    # 3. Rutas de tu Aplicación 'mi_finanzas'
    path('', include(('mi_finanzas.urls', 'mi_finanzas'), namespace='mi_finanzas')),
]

