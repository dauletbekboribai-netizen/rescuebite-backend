from contextlib import asynccontextmanager
import warnings

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette import status

from app.api import admin, auth, batches, donations, orders, restaurants, routes, users
from app.core.config import get_settings

warnings.filterwarnings('ignore', category=DeprecationWarning)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print('App started')
    yield
    print('App stopped')


app = FastAPI(
    title='RescueBite API',
    version='1.1.0',
    description='Production-grade RescueBite backend with restaurant operations, inventory expiry, reservations, and manual seller-confirmed payments.',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type'],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={'code': 'internal_error', 'message': 'unexpected server error'})


@app.get('/health', tags=['health'])
def health():
    return {'status': 'ok'}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(restaurants.router)
app.include_router(batches.router)
app.include_router(orders.router)
app.include_router(donations.router)
app.include_router(routes.router)
app.include_router(admin.router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema.setdefault('components', {}).setdefault('securitySchemes', {})['BearerAuth'] = {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}
    schema.setdefault('components', {}).setdefault('schemas', {})['ErrorResponse'] = {
        'type': 'object',
        'properties': {'code': {'type': 'string'}, 'message': {'type': 'string'}},
        'required': ['code', 'message'],
        'example': {'code': 'forbidden', 'message': 'insufficient role'},
    }
    for path, methods in schema.get('paths', {}).items():
        for method, operation in methods.items():
            if method not in {'get', 'post', 'put', 'patch', 'delete'}:
                continue
            if not path.startswith('/auth/register') and not path.startswith('/auth/login') and path != '/health':
                operation.setdefault('security', [{'BearerAuth': []}])
            responses = operation.setdefault('responses', {})
            for code in ['400', '401', '403', '404', '409', '422', '500']:
                responses.setdefault(code, {'description': f'Standard {code} error', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/ErrorResponse'}}}})
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
