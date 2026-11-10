from pathlib import Path

import environ


# =========================================================
# 기본 경로 / 환경변수
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEPLOY=(bool, False),
    DEBUG=(bool, True),
)

# manage.py와 같은 폴더의 .env를 읽는다.
# 실제 키/비밀번호는 settings.py에 직접 작성하지 않는다.
environ.Env.read_env(
    BASE_DIR / ".env"
)

DEPLOY = env.bool(
    "DEPLOY",
    default=False,
)

DEBUG = env.bool(
    "DEBUG",
    default=not DEPLOY,
)


# =========================================================
# 보안 / 호스트
# =========================================================

# 운영(AWS 서버)에서는 반드시 .env에 SECRET_KEY를 넣는다.
# 로컬 개발에서는 .env가 없어도 서버가 켜지도록 개발 전용 fallback만 둔다.
if DEPLOY:
    SECRET_KEY = env("SECRET_KEY")
else:
    SECRET_KEY = env(
        "SECRET_KEY",
        default="django-insecure-local-development-only-change-me",
    )

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "127.0.0.1",
        "localhost",
    ],
)

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)


# =========================================================
# 외부 API KEY
# =========================================================

# 브라우저에서 사용하는 Web / JavaScript 키
KAKAO_MAP_API_KEY = env(
    "KAKAO_MAP_API_KEY",
    default="",
)

# 서버에서만 사용하는 REST 키
# context processor나 HTML에 전달하지 않는다.
KAKAO_REST_API_KEY = env(
    "KAKAO_REST_API_KEY",
    default="",
)

TOUR_API_KEY = env(
    "TOUR_API_KEY",
    default="",
)


# =========================================================
# AI 대화 (여행 만들기 챗봇)
#
# OpenAI 호환 API 이면 무엇이든 쓸 수 있다.
#   OpenAI : https://api.openai.com/v1
#   Ollama : http://localhost:11434/v1  (키 불필요)
# =========================================================
AI_BASE_URL = env(
    "AI_BASE_URL",
    default="https://api.openai.com/v1",
)

AI_API_KEY = env(
    "AI_API_KEY",
    default="",
)

AI_MODEL = env(
    "AI_MODEL",
    default="gpt-4o-mini",
)

# 기본 모델이 바쁠 때 대신 쓸 모델들 (쉼표로 구분, 비워도 됨)
AI_FALLBACK_MODELS = env(
    "AI_FALLBACK_MODELS",
    default="",
)

AI_TIMEOUT = env.int(
    "AI_TIMEOUT",
    default=40,
)

# 기본 AI(예: 이 PC의 Ollama)가 꺼졌거나 응답이 없을 때 넘어갈 곳 (예: OpenAI). 비우면 안 넘어감
AI_BACKUP_BASE_URL = env(
    "AI_BACKUP_BASE_URL",
    default="",
)

AI_BACKUP_API_KEY = env(
    "AI_BACKUP_API_KEY",
    default="",
)

AI_BACKUP_MODEL = env(
    "AI_BACKUP_MODEL",
    default="",
)

# 임베딩 모델 (설정 A: OpenAI / 설정 B:bge-m3)
AI_EMBED_MODEL = env("AI_EMBED_MODEL", default="text-embedding-3-small")


# =========================================================
# Application definition
# =========================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "sherpaapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pj_django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "sherpaapp.context_processors.login_member",
                "sherpaapp.context_processors.kakao_api_key",
            ],
        },
    },
]

WSGI_APPLICATION = "pj_django.wsgi.application"


# =========================================================
# Database
# =========================================================

# 로컬·서버 모두 MariaDB, 접속 정보는 .env의 DB_*
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env(
            "DB_NAME",
            default="sherpa_schema",
        ),
        "USER": env(
            "DB_USER",
            default="sherpa",
        ),
        "PASSWORD": env(
            "DB_PASSWORD",
            default="",
        ),
        "HOST": env(
            "DB_HOST",
            default="127.0.0.1",
        ),
        "PORT": env(
            "DB_PORT",
            default="3306",
        ),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


# =========================================================
# Cache (외부 API 결과 저장: 관광공사 운영시간·요금·사진, 날씨, 카카오 경로 등)
#
# DB 표(django_cache)에 저장한다. 기본값(프로세스 메모리)은
#   - 서버의 gunicorn 프로세스 3개가 따로 가지고
#   - 배포·재시작 때마다 지워져서
# "7일 캐시"가 실제로는 오래 가지 못했다.
# 표는 마이그레이션 0015가 만든다 (migrate만 하면 됨).
# 시험하다 지우고 싶으면:
#   python manage.py shell -c "from django.core.cache import cache; cache.clear()"
# =========================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "TIMEOUT": 300,  # 시간을 따로 안 주면 5분 (각 서비스는 보통 직접 정함)
        "OPTIONS": {
            "MAX_ENTRIES": 50000,  # 넘으면 오래된 것부터 1/3 지움
        },
    }
}


# =========================================================
# Password validation
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# Internationalization
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Seoul"

USE_I18N = True

# 현재 프로젝트의 기존 동작을 유지한다.
USE_TZ = False


# =========================================================
# Static / Media
# =========================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# Session / browser
# =========================================================

SESSION_COOKIE_AGE = env.int(
    "SESSION_COOKIE_AGE",
    default=1800,
)

SESSION_SAVE_EVERY_REQUEST = env.bool(
    "SESSION_SAVE_EVERY_REQUEST",
    default=True,
)

# 외부 지도·API 호출 때 Referer 전달 방식 (카카오 지도 JS 키 도메인 확인에 필요)
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# 필요하면 운영 .env에서 True로 전환할 수 있다.
SESSION_COOKIE_SECURE = env.bool(
    "SESSION_COOKIE_SECURE",
    default=False,
)

CSRF_COOKIE_SECURE = env.bool(
    "CSRF_COOKIE_SECURE",
    default=False,
)

# 메일 (비밀번호 찾기 인증 코드)
# .env에 EMAIL_HOST_USER가 없으면 메일을 실제로 보내지 않고 runserver 터미널에 찍는다
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "TRIPA <no-reply@tripa.local>")

# =========================================================
# 기타
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
