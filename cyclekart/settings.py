from pathlib import Path
from decouple import config
import dj_database_url
# import logging

# logging.basicConfig(level=logging.DEBUG)

TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------ Security ------------------
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)


# ------------------Razorpay---------------------
RAZORPAY_KEY_ID = config("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = config("RAZORPAY_KEY_SECRET")

SECURE_CROSS_ORIGIN_OPENER_POLICY="same-origin-allow-popups"


ALLOWED_HOSTS = ['*']

# ------------------ Installed Apps ------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'django.contrib.sites',  # Required for allauth

    # Allauth apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Your apps
    'userapp',
    'adminapp',
    'widget_tweaks',
]

SITE_ID = 1

# ------------------ Middleware ------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'adminapp.middleware.DisableAdminCacheMiddleware',
    'userapp.middleware.NoCacheForAuthenticatedMiddleware',
    'userapp.middleware.BlockedUserMiddleware',
]

# ------------------ URL and WSGI ------------------
ROOT_URLCONF = 'cyclekart.urls'
WSGI_APPLICATION = 'cyclekart.wsgi.application'

# ------------------ Templates ------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # Required by allauth
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'userapp.context_processors.cart_wishlist_counts',
            ],
        },
    },
]

# ------------------ Database ------------------
DATABASES = {
    'default': {
        # dj_database_url.parse(config("DATABASE_URL"))
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
    
}



# ------------------ Custom User Model ------------------
AUTH_USER_MODEL = 'userapp.CustomUser'

# ------------------ Authentication Backends ------------------
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ------------------ Allauth Redirects ------------------
LOGIN_URL = 'user_login'
LOGIN_REDIRECT_URL = 'user_home'
LOGOUT_REDIRECT_URL = 'user_login'


LOGIN_REDIRECT_URL = '/user_home/'
ACCOUNT_LOGIN_REDIRECT_URL = '/user_home/'
ACCOUNT_SIGNUP_REDIRECT_URL = '/user_home/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/user_login/'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 30  
SESSION_SAVE_EVERY_REQUEST = True



ACCOUNT_EMAIL_VERIFICATION = 'none'  



# ------------------ Email Settings ------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# For password reset emails
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ACCOUNT_FORMS = {
    'reset_password': 'allauth.account.forms.ResetPasswordForm',
}

# ------------------ Allauth Core Settings ------------------
# ACCOUNT_AUTHENTICATION_METHOD = 'email'
# ACCOUNT_EMAIL_REQUIRED = True
# ACCOUNT_USERNAME_REQUIRED = False
# ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_VERIFICATION = 'none'


# ------------------ Allauth Social Settings ------------------
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',
        }
    }
}



#  Custom adapters to skip confirmation and auto-link Google to email
ACCOUNT_ADAPTER = 'userapp.adapters.NoNewUsersAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'userapp.adapters.AutoConnectSocialAccountAdapter'


# ------------------ Password Validators ------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------ Localization ------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ------------------ Static Files ------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'staticfiles',   # ✅ this must match your folder name
]
STATIC_ROOT = BASE_DIR / 'static'  # for collectstatic (optional in dev)

# Cloudinary config (keep as-is)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET')
}

# NEW: STORAGES for Django 5.1+ (replaces DEFAULT_FILE_STORAGE)
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",  # Keeps static local
    },
}


MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ------------------ Auto Field ------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
