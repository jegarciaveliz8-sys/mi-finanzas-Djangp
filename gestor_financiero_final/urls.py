from django.contrib import admin
from django.urls import path, include
from django.conf import settings # <--- 1. ¡IMPORTA SETTINGS!
from django.contrib.auth import urls as auth_urls 

# 🛑 CORRECCIÓN CRÍTICA: Importamos 'RegistroUsuario', NO 'RegistroUsuarioView'.
# Se asume que esta importación es correcta para tu app.
from mi_finanzas.views import RegistroUsuario 

urlpatterns = [
    # Ruta de Administración
    path('admin/', admin.site.urls),

    # 1. Rutas de Autenticación de Django (login, logout, etc.)
    # Define los patrones 'auth:login', 'auth:logout', etc.
    path('accounts/', include((auth_urls, 'auth'), namespace='auth')), 

    # 2. Rutas de Registro (CRÍTICO: Define el patrón 'signup')
    # Usamos la clase corregida: RegistroUsuario.as_view()
    path('accounts/signup/', RegistroUsuario.as_view(), name='signup'), 

    # 3. Rutas de tu Aplicación 'mi_finanzas'
    path('', include(('mi_finanzas.urls', 'mi_finanzas'), namespace='mi_finanzas')),
]


# 💡 CONFIGURACIÓN DE DEPURACIÓN (Solo se añade si DEBUG es True)
if settings.DEBUG: # <--- 2. ¡ENVUELVE LA RUTA EN ESTA CONDICIÓN!
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")), 
    ]

