"""
GraphQL endpoint for Janua API.
"""

from fastapi import APIRouter, Depends, Request, WebSocket, BackgroundTasks
from fastapi.responses import HTMLResponse
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.graphql.schema import schema
from app.config import settings


router = APIRouter(tags=["graphql"])


async def get_context(
    request: Request = None,
    websocket: WebSocket = None,
    background_tasks: BackgroundTasks = None,
    db = Depends(get_db),
    current_user = Depends(get_current_user_optional)
) -> dict:
    """
    Create context for GraphQL resolvers.
    """
    context = {
        "db": db,
        "user": current_user,
        "tenant_id": str(current_user.tenant_id) if current_user else None,
        "request": request,
        "websocket": websocket,
        "background_tasks": background_tasks
    }
    
    # Add request metadata if available
    if request:
        context.update({
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent")
        })
    
    return context


# Create GraphQL app with custom context
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
)

# Mount GraphQL endpoint
router.include_router(graphql_app, prefix="/graphql")


# GraphQL Playground (for development)
@router.get("/graphql-playground", response_class=HTMLResponse)
async def graphql_playground():
    """
    Serve GraphQL Playground UI (development only).
    """
    if not settings.DEBUG:
        return HTMLResponse("GraphQL Playground is disabled in production", status_code=404)
    
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Janua GraphQL Playground</title>
        <link rel="stylesheet" href="https://unpkg.com/graphql-playground-react/build/static/css/index.css" />
        <script src="https://unpkg.com/graphql-playground-react/build/static/js/middleware.js"></script>
    </head>
    <body>
        <div id="root"></div>
        <script>
            window.addEventListener('load', function (event) {
                GraphQLPlayground.init(document.getElementById('root'), {
                    endpoint: '/graphql',
                    subscriptionEndpoint: 'ws://localhost:8000/graphql',
                    settings: {
                        'request.credentials': 'include',
                        'editor.theme': 'dark',
                        'editor.fontSize': 14,
                        'editor.reuseHeaders': true,
                        'tracing.hideTracingResponse': false,
                        'schema.polling.enable': true,
                        'schema.polling.interval': 2000
                    }
                })
            })
        </script>
    </body>
    </html>
    """)


# GraphQL schema introspection endpoint (for tooling)
@router.get("/graphql/schema")
async def get_graphql_schema():
    """
    Get GraphQL schema in SDL format.
    """
    return {
        "schema": str(schema)
    }


# Health check for GraphQL endpoint
@router.get("/graphql/health")
async def graphql_health():
    """
    Check GraphQL endpoint health.
    """
    return {
        "status": "healthy",
        "endpoint": "/graphql",
        "playground": "/graphql-playground" if settings.DEBUG else None,
        "subscriptions": "enabled",
        "introspection": settings.DEBUG
    }