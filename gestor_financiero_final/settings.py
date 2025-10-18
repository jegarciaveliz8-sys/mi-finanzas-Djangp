"""
Configuración de Django para el proyecto gestor_financiero_final.
CONFIGURACIÓN CORREGIDA PARA DESPLIEGUE GRATUITO EN NUBE (Render/Railway).
"""

from pathlib import Path
import os  # <<-- IMPORTACIÓN DE OS NECESARIA
from django.utils.translation import gettext_lazy as _

# Construye paths dentro del proyecto: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# SEGURIDAD Y DEPURACIÓN
# ----------------------------------------------------------------------

# ⚠️ CLAVE SECRETA: En producción, debe ser cargada desde una variable de entorno.
SECRET_KEY = 'django-insecure-33^d*8(2f!7&y(f8k5g*s!0f2j00+c2w2m1f8$20e=g0k0a0p'

# ⚠️ DEBUG: Cambiar a False ANTES DE DEPLOYAR para evitar exponer errores.
DEBUG = True # Mantenemos TRUE por ahora, pero CÁMBIALO a FALSE antes del push final

# ⚠️ ALLOWED_HOSTS: ¡CRÍTICO PARA DESPLIEGUE GRATUITO!
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.onrender.com', '.railway.app', '*'] 
# El '*' es un comodín para desarrollo/demos, pero se debe usar el subdominio real.

# 💡 CONFIGURACIÓN PARA DJANGO DEBUG TOOLBAR (ELIMINADO en Producción)
INTERNAL_IPS = [
        "127.0.0.1", 
]


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
        
        # AÑADIR WhiteNoise si lo necesitas para servir estáticos sin CDN
        'whitenoise.runserver_nostatic', # <<-- NUEVO: para que funcione con el runserver local
        'django.contrib.staticfiles',

        # 💡 HERRAMIENTAS DE DEPURACIÓN Y ESTILO
        # 'debug_toolbar', # <<-- ELIMINADO para producción
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
        'whitenoise.middleware.WhiteNoiseMiddleware', # <<-- CRÍTICO: Para servir estáticos

        # 'debug_toolbar.middleware.DebugToolbarMiddleware', # <<-- ELIMINADO

        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'gestor_financiero_final.urls'


# ... (Resto de las secciones TEMPLATES, WSGI, DATABASES, AUTENTICACIÓN sin cambios) ...

# ----------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA (CORREGIDO para PRODUCCIÓN)
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

# ... (Resto del archivo sin cambios) ...
