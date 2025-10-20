"""
Configuración de Django para el proyecto gestor_financiero_final.
CONFIGURACIÓN CORREGIDA PARA DESPLIEGUE GRATUITO EN NUBE (Render/Railway).
"""

from pathlib import Path
import os
from django.utils.translation import gettext_lazy as _

# Construye paths dentro del proyecto: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# SEGURIDAD Y DEPURACIÓN
# ----------------------------------------------------------------------

# ⚠️ CLAVE SECRETA: En producción, debe ser cargada desde una variable de entorno.
SECRET_KEY = 'django-insecure-33^d*8(2f!7&y(f8k5g*s!0f2j00+c2w2m1f8$20e=g0k0a0p'

# ⚠️ DEBUG: Cambiar a False ANTES DE DEPLOYAR para evitar exponer errores.
DEBUG = True

# ⚠️ ALLOWED_HOSTS: ¡CRÍTICO PARA DESPLIEGUE GRATUITO!
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.onrender.com', '.railway.app', '*'] 

# ⭐ NECESARIO PARA DJANGO DEBUG TOOLBAR
INTERNAL_IPS = [
    "127.0.0.1",
    "::1",
]


# ----------------------------------------------------------------------
# CONFIGURACIÓN DE AUTENTICACIÓN (2FA)
# ----------------------------------------------------------------------

# 💥 Define la URL de login para usar el formulario de two_factor
LOGIN_URL = 'two_factor:login'
# 💥 Redirección después del inicio de sesión (y después de 2FA)
LOGIN_REDIRECT_URL = '/'


# ----------------------------------------------------------------------
# APLICACIONES REGISTRADAS
# ----------------------------------------------------------------------

INSTALLED_APPS = [
    # Aplicaciones Core de Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    
    # 💥 NUEVO: Dependencias de Two Factor Auth
    'django_otp',
    'django_otp.plugins.otp_static',
    'django_otp.plugins.otp_totp',
    'two_factor',
    'two_factor.plugins.phonenumber', # Opcional: para métodos basados en teléfono

    # CRÍTICO: Configuración de Debug Toolbar
    'debug_toolbar',

    # AÑADIR WhiteNoise para servir estáticos sin CDN
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',

    # 💡 HERRAMIENTAS DE ESTILO
    'django.contrib.humanize',

    # ✅ LIBRERÍAS DE FORMULARIOS
    'crispy_forms', 
    'widget_tweaks', 
    'crispy_bootstrap5',

    # Mis aplicaciones locales
    'mi_finanzas', 
]


# ----------------------------------------------------------------------
# MIDDLEWARE
# ----------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    
    # CRÍTICO: debug_toolbar debe ir después de SecurityMiddleware
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    
    'whitenoise.middleware.WhiteNoiseMiddleware', # CRÍTICO: Para servir estáticos

    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # 💥 NUEVO: Middleware de Two Factor Auth
    'django_otp.middleware.OTPMiddleware',
    
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ----------------------------------------------------------------------
# CONFIGURACIÓN DE DJANGO TWO-FACTOR-AUTH
# ----------------------------------------------------------------------

TWO_FACTOR_FORMS = {
    # Usa el formulario de login de Two Factor para aplicar el 2FA
    'login': 'two_factor.forms.TwoFactorAuthenticationForm',
}

# (Opcional, si usas SMS con Twilio, puedes comentarlo o dejarlo por ahora)
# TWO_FACTOR_GATEWAY = 'two_factor.gateways.Twilio'


ROOT_URLCONF = 'gestor_financiero_final.urls'


# ----------------------------------------------------------------------
# PLANTILLAS (TEMPLATES)
# ----------------------------------------------------------------------

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # DIRS: El directorio 'templates' global del proyecto.
        'DIRS': [BASE_DIR / 'templates'], 
        # APP_DIRS: CRÍTICO.
        'APP_DIRS': True, 
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ----------------------------------------------------------------------
# BASE DE DATOS
# ----------------------------------------------------------------------

DATABASES = {
    'default': {
        # Configuración por defecto usando SQLite para tests y desarrollo local
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ----------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# ----------------------------------------------------------------------

STATIC_URL = 'static/'

# ¡NUEVO! Directorios donde Django buscará archivos estáticos en desarrollo.
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
] 

# CRÍTICO: Directorio donde collectstatic recolecta los archivos para el servidor
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 

# CRÍTICO: Usa el motor de almacenamiento de WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage' 


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ----------------------------------------------------------------------
# CONFIGURACIONES ADICIONALES
# ----------------------------------------------------------------------

# Necesarias para crispy_forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

🚨 Pasos Obligatorios Ahora

Después de reemplazar el archivo settings.py con este código, debes ejecutar lo siguiente en orden:

    Migraciones: Se necesita crear las tablas para debug_toolbar, django_otp y two_factor.
    Bash

(venv) ➜ mi_nuevo_proyecto python manage.py migrate

Configurar URLs: Asegúrate de que tu urls.py principal incluya las URLs de two_factor (consulta el Paso 3 del plan anterior si tienes dudas).
Python

# gestor_financiero_final/urls.py (Ejemplo)

from django.urls import path, include
from two_factor.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Opcional: Reemplaza el login de Django con el de 2FA
    path('accounts/login/', LoginView.as_view(), name='login'),

    # CRÍTICO: Incluir todas las rutas de configuración y manejo de 2FA
    path('', include('two_factor.urls', 'two_factor')),

    # ... otras URLs
]
