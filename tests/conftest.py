import os
os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_rescuebite.db')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET_KEY', 'test-access-secret-key-that-is-long')
os.environ.setdefault('JWT_REFRESH_SECRET_KEY', 'test-refresh-secret-key-that-is-long')
os.environ.setdefault('ALLOWED_ORIGINS', 'http://localhost:3000')
