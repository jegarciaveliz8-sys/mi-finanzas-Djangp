"""
Configuración de Django para el proyecto gestor_financiero_final.
"""

from pathlib import Path
import os 

# Construye paths dentro del proyecto: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# SEGURIDAD Y DEPURACIÓN
# ----------------------------------------------------------------------

# ⚠️ CLAVE SECRETA: En producción, debe ser cargada desde una variable de entorno.
SECRET_KEY = 'django-insecure-33^d*8(2f!7&y(f8k5g*s!0f2j00+c2w2m1f8$20e=g0k0a0p'

# ⚠️ DEBUG: Cambiar a False ANTES DE DEPLOYAR para evitar exponer errores.
DEBUG = True

# ⚠️ ALLOWED_HOSTS: Añadir tu dominio o IP del servidor en producción.
ALLOWED_HOSTS = ['127.0.0.1', '192.168.1.39', 'localhost', '0.0.0.0'] 

# 💡 CONFIGURACIÓN PARA DJANGO DEBUG TOOLBAR
# Estas IPs tienen permiso para ver la barra de depuración.
INTERNAL_IPS = [
	"127.0.0.1", 
	"192.168.1.39",
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
	'django.contrib.staticfiles',
	
	# 💡 HERRAMIENTA DE DEPURACIÓN
	'debug_toolbar', 
	
	# ✅ Necesario para resolver el ModuleNotFoundError
	'django_bootstrap5', 

	'crispy_bootstrap5',
	# Herramientas de terceros
	# 'widget_tweaks',  <-- 🛑 COMENTADO: No es compatible con tu versión de Python/pip.
	'django.contrib.humanize',
	
	# Mis aplicaciones
	'mi_finanzas', 
	'crispy_forms', 
]


# ----------------------------------------------------------------------
# MIDDLEWARE
# ----------------------------------------------------------------------

MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	
	# 💡 MIDDLEWARE DE DEPURACIÓN (Debe estar aquí, después de SecurityMiddleware)
	'debug_toolbar.middleware.DebugToolbarMiddleware', 
	
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	
]


ROOT_URLCONF = 'gestor_financiero_final.urls'


# ----------------------------------------------------------------------
# PLANTILLAS (TEMPLATES)
# ----------------------------------------------------------------------

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		# Carpeta 'templates' en la raíz para base.html
		'DIRS': [BASE_DIR / 'templates'], 
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

WSGI_APPLICATION = 'gestor_financiero_final.wsgi.application'


# ----------------------------------------------------------------------
# BASE DE DATOS (SQLite CORREGIDA para despliegue actual)
# ----------------------------------------------------------------------

DATABASES = {
	'default': {
		# CRÍTICO: Usar SQLite para eliminar el fallo de conexión a PostgreSQL.
		'ENGINE': 'django.db.backends.sqlite3',
		'NAME': BASE_DIR / 'db.sqlite3',
	}
}


# ----------------------------------------------------------------------
# AUTENTICACIÓN Y REDIRECCIÓN
# ----------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
	{
		'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
	},
]

# URL a la que se redirige a usuarios no autenticados.
LOGIN_URL = 'auth:login' 

# Redirige después de iniciar sesión a tu panel principal.
LOGIN_REDIRECT_URL = 'mi_finanzas:resumen_financiero'

# Redirige después de cerrar sesión.
LOGOUT_REDIRECT_URL = 'auth:login'


# ----------------------------------------------------------------------
# INTERNACIONALIZACIÓN Y ZONA HORARIA
# ----------------------------------------------------------------------

LANGUAGE_CODE = 'es-es'

TIME_ZONE = 'America/Guatemala' 
USE_I18N = True
USE_TZ = True


# ----------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA (CORREGIDO para PRODUCCIÓN)
# ----------------------------------------------------------------------

STATIC_URL = 'static/'
# CRÍTICO: Directorio donde collectstatic recolecta los archivos para Nginx
STATIC_ROOT = BASE_DIR / 'staticfiles' 


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5" 



# =============================================================
# CONFIGURACIÓN DE SEGURIDAD PARA CARGAR CDN (solución final)
# =============================================================
