"""
SDK-focused API documentation generation and enhancement.

Extends FastAPI's OpenAPI generation with SDK-specific metadata,
examples, and platform-specific code generation hints.
"""

from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import json


class SDKPlatform(str, Enum):
    """Supported SDK platforms for code generation."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    JAVA = "java"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"


class CodeExample(BaseModel):
    """Code example for a specific platform."""
    platform: SDKPlatform
    title: str
    description: Optional[str] = None
    code: str
    imports: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None


class SDKMethodInfo(BaseModel):
    """Enhanced method information for SDK generation."""
    method_name: str  # SDK method name (may differ from endpoint)
    description: str
    is_async: bool = True
    returns_paginated: bool = False
    requires_auth: bool = True
    rate_limited: bool = True
    idempotent: bool = False
    bulk_operation: bool = False
    examples: List[CodeExample] = []
    platform_specific: Dict[SDKPlatform, Dict[str, Any]] = {}


class SDKModelInfo(BaseModel):
    """Enhanced model information for SDK generation."""
    class_name: str  # SDK class name
    description: str
    is_request_model: bool = False
    is_response_model: bool = False
    is_enum: bool = False
    validation_rules: Dict[str, Any] = {}
    platform_specific: Dict[SDKPlatform, Dict[str, Any]] = {}


class APIDocumentationEnhancer:
    """
    Enhances FastAPI OpenAPI documentation with SDK-specific information.

    This class adds metadata, examples, and platform-specific hints that
    make the generated OpenAPI spec more suitable for SDK code generation.
    """

    def __init__(self, app: FastAPI):
        self.app = app
        self.sdk_methods: Dict[str, SDKMethodInfo] = {}
        self.sdk_models: Dict[str, SDKModelInfo] = {}
        self._platform_examples: Dict[str, List[CodeExample]] = {}

    def add_method_info(self, endpoint_id: str, method_info: SDKMethodInfo) -> None:
        """Add SDK-specific method information for an endpoint."""
        self.sdk_methods[endpoint_id] = method_info

    def add_model_info(self, model_name: str, model_info: SDKModelInfo) -> None:
        """Add SDK-specific model information."""
        self.sdk_models[model_name] = model_info

    def add_code_example(self, endpoint_id: str, example: CodeExample) -> None:
        """Add a code example for a specific endpoint."""
        if endpoint_id not in self._platform_examples:
            self._platform_examples[endpoint_id] = []
        self._platform_examples[endpoint_id].append(example)

    def generate_enhanced_openapi(self) -> Dict[str, Any]:
        """
        Generate enhanced OpenAPI specification with SDK metadata.

        Returns:
            Enhanced OpenAPI specification suitable for SDK generation
        """
        # Get base OpenAPI spec
        openapi_spec = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )

        # Add SDK-specific extensions
        openapi_spec["x-sdk-config"] = self._generate_sdk_config()
        openapi_spec["x-code-samples"] = self._generate_code_samples()
        openapi_spec["x-sdk-models"] = self._generate_sdk_models()

        # Enhance existing paths with SDK information
        if "paths" in openapi_spec:
            self._enhance_paths(openapi_spec["paths"])

        # Add SDK-specific components
        if "components" in openapi_spec:
            self._enhance_components(openapi_spec["components"])

        return openapi_spec

    def _generate_sdk_config(self) -> Dict[str, Any]:
        """Generate SDK configuration metadata."""
        return {
            "supported_platforms": [platform.value for platform in SDKPlatform],
            "default_timeout": 30,
            "default_retry_attempts": 3,
            "rate_limiting": {
                "enabled": True,
                "default_limit": 100,
                "default_window": 3600
            },
            "authentication": {
                "methods": ["api_key", "jwt_token", "oauth2"],
                "default_method": "jwt_token",
                "token_refresh": True
            },
            "pagination": {
                "default_page_size": 20,
                "max_page_size": 100,
                "style": "cursor_based"
            }
        }

    def _generate_code_samples(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate code samples for each endpoint."""
        samples = {}

        for endpoint_id, examples in self._platform_examples.items():
            samples[endpoint_id] = [
                {
                    "lang": example.platform.value,
                    "label": example.title,
                    "source": example.code,
                    "description": example.description,
                    "imports": example.imports,
                    "dependencies": example.dependencies
                }
                for example in examples
            ]

        return samples

    def _generate_sdk_models(self) -> Dict[str, Dict[str, Any]]:
        """Generate SDK model metadata."""
        models = {}

        for model_name, model_info in self.sdk_models.items():
            models[model_name] = {
                "class_name": model_info.class_name,
                "description": model_info.description,
                "type": self._get_model_type(model_info),
                "validation_rules": model_info.validation_rules,
                "platform_specific": {
                    platform.value: config
                    for platform, config in model_info.platform_specific.items()
                }
            }

        return models

    def _get_model_type(self, model_info: SDKModelInfo) -> str:
        """Determine the model type for SDK generation."""
        if model_info.is_enum:
            return "enum"
        elif model_info.is_request_model:
            return "request"
        elif model_info.is_response_model:
            return "response"
        else:
            return "data"

    def _enhance_paths(self, paths: Dict[str, Any]) -> None:
        """Enhance path definitions with SDK-specific information."""
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    operation_id = operation.get("operationId")
                    if operation_id in self.sdk_methods:
                        self._enhance_operation(operation, self.sdk_methods[operation_id])

    def _enhance_operation(self, operation: Dict[str, Any], method_info: SDKMethodInfo) -> None:
        """Enhance a single operation with SDK information."""
        # Add SDK-specific metadata
        operation["x-sdk-method-name"] = method_info.method_name
        operation["x-sdk-async"] = method_info.is_async
        operation["x-sdk-paginated"] = method_info.returns_paginated
        operation["x-sdk-auth-required"] = method_info.requires_auth
        operation["x-sdk-rate-limited"] = method_info.rate_limited
        operation["x-sdk-idempotent"] = method_info.idempotent
        operation["x-sdk-bulk-operation"] = method_info.bulk_operation

        # Add platform-specific configuration
        if method_info.platform_specific:
            operation["x-sdk-platform-config"] = {
                platform.value: config
                for platform, config in method_info.platform_specific.items()
            }

        # Add code examples if available
        operation_id = operation.get("operationId")
        if operation_id in self._platform_examples:
            operation["x-code-samples"] = [
                {
                    "lang": example.platform.value,
                    "label": example.title,
                    "source": example.code
                }
                for example in self._platform_examples[operation_id]
            ]

    def _enhance_components(self, components: Dict[str, Any]) -> None:
        """Enhance component definitions with SDK information."""
        if "schemas" in components:
            for schema_name, schema_def in components["schemas"].items():
                if schema_name in self.sdk_models:
                    model_info = self.sdk_models[schema_name]
                    schema_def["x-sdk-class-name"] = model_info.class_name
                    schema_def["x-sdk-type"] = self._get_model_type(model_info)

                    if model_info.platform_specific:
                        schema_def["x-sdk-platform-config"] = {
                            platform.value: config
                            for platform, config in model_info.platform_specific.items()
                        }


def create_platform_examples() -> Dict[str, List[CodeExample]]:
    """Create platform-specific code examples for common operations."""
    examples = {}

    # Authentication examples
    examples["auth_signin"] = [
        CodeExample(
            platform=SDKPlatform.PYTHON,
            title="Sign In with Python",
            description="Authenticate a user with email and password",
            code="""
from janua import JanuaClient

client = JanuaClient(base_url="https://api.janua.dev")

try:
    response = await client.auth.sign_in(
        email="user@example.com",
        password="secure_password"
    )

    # Store tokens for future requests
    client.token_manager.store_tokens(
        access_token=response.data.access_token,
        refresh_token=response.data.refresh_token,
        expires_in=response.data.expires_in
    )

    print(f"Welcome, {response.data.user.email}!")

except ValidationError as e:
    print(f"Validation failed: {e.validation_errors}")
except AuthenticationError as e:
    print(f"Authentication failed: {e.message}")
            """,
            imports=["from janua import JanuaClient", "from janua.exceptions import ValidationError, AuthenticationError"],
            dependencies=["janua>=1.0.0"]
        ),

        CodeExample(
            platform=SDKPlatform.TYPESCRIPT,
            title="Sign In with TypeScript",
            description="Authenticate a user with email and password",
            code="""
import { JanuaClient, ValidationError, AuthenticationError } from '@janua/typescript-sdk';

const client = new JanuaClient({
  baseUrl: 'https://api.janua.dev'
});

try {
  const response = await client.auth.signIn({
    email: 'user@example.com',
    password: 'secure_password'
  });

  // Tokens are automatically stored by the client
  console.log(`Welcome, ${response.data.user.email}!`);

} catch (error) {
  if (error instanceof ValidationError) {
    console.error('Validation failed:', error.validationErrors);
  } else if (error instanceof AuthenticationError) {
    console.error('Authentication failed:', error.message);
  }
}
            """,
            imports=["@janua/typescript-sdk"],
            dependencies=["@janua/typescript-sdk@^1.0.0"]
        ),

        CodeExample(
            platform=SDKPlatform.GO,
            title="Sign In with Go",
            description="Authenticate a user with email and password",
            code="""
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/madfam-io/go-sdk/client"
    "github.com/madfam-io/go-sdk/auth"
)

func main() {
    client := client.NewJanuaClient(&client.Config{
        BaseURL: "https://api.janua.dev",
    })

    request := &auth.SignInRequest{
        Email:    "user@example.com",
        Password: "secure_password",
    }

    response, err := client.Auth.SignIn(context.Background(), request)
    if err != nil {
        if validationErr, ok := err.(*client.ValidationError); ok {
            log.Printf("Validation failed: %v", validationErr.ValidationErrors)
        } else if authErr, ok := err.(*client.AuthenticationError); ok {
            log.Printf("Authentication failed: %s", authErr.Message)
        } else {
            log.Printf("Error: %v", err)
        }
        return
    }

    fmt.Printf("Welcome, %s!\\n", response.Data.User.Email)
}
            """,
            imports=["github.com/madfam-io/go-sdk"],
            dependencies=["github.com/madfam-io/go-sdk@v1.0.0"]
        )
    ]

    # User management examples
    examples["users_get_me"] = [
        CodeExample(
            platform=SDKPlatform.PYTHON,
            title="Get Current User (Python)",
            code="""
user = await client.users.get_me()
print(f"User ID: {user.data.id}")
print(f"Email: {user.data.email}")
print(f"Verified: {user.data.email_verified}")
            """
        ),

        CodeExample(
            platform=SDKPlatform.TYPESCRIPT,
            title="Get Current User (TypeScript)",
            code="""
const user = await client.users.getMe();
console.log(`User ID: ${user.data.id}`);
console.log(`Email: ${user.data.email}`);
console.log(`Verified: ${user.data.emailVerified}`);
            """
        )
    ]

    # Organization examples
    examples["organizations_create"] = [
        CodeExample(
            platform=SDKPlatform.PYTHON,
            title="Create Organization (Python)",
            code="""
org = await client.organizations.create(
    name="My Company",
    slug="my-company",
    description="Our company organization"
)
print(f"Created organization: {org.data.name}")
            """
        ),

        CodeExample(
            platform=SDKPlatform.TYPESCRIPT,
            title="Create Organization (TypeScript)",
            code="""
const org = await client.organizations.create({
  name: 'My Company',
  slug: 'my-company',
  description: 'Our company organization'
});
console.log(`Created organization: ${org.data.name}`);
            """
        )
    ]

    return examples


def setup_sdk_documentation(app: FastAPI) -> APIDocumentationEnhancer:
    """
    Set up SDK-enhanced documentation for a FastAPI application.

    Args:
        app: FastAPI application instance

    Returns:
        Configured documentation enhancer
    """
    enhancer = APIDocumentationEnhancer(app)

    # Add common method information
    enhancer.add_method_info("auth_signin", SDKMethodInfo(
        method_name="sign_in",
        description="Authenticate a user with email and password",
        is_async=True,
        requires_auth=False,
        rate_limited=True,
        platform_specific={
            SDKPlatform.PYTHON: {"method_name": "sign_in"},
            SDKPlatform.TYPESCRIPT: {"method_name": "signIn"},
            SDKPlatform.GO: {"method_name": "SignIn"},
            SDKPlatform.JAVA: {"method_name": "signIn"},
        }
    ))

    enhancer.add_method_info("users_get_me", SDKMethodInfo(
        method_name="get_me",
        description="Get current authenticated user information",
        is_async=True,
        requires_auth=True,
        platform_specific={
            SDKPlatform.PYTHON: {"method_name": "get_me"},
            SDKPlatform.TYPESCRIPT: {"method_name": "getMe"},
            SDKPlatform.GO: {"method_name": "GetMe"},
        }
    ))

    enhancer.add_method_info("organizations_list", SDKMethodInfo(
        method_name="list",
        description="List organizations with pagination",
        is_async=True,
        returns_paginated=True,
        requires_auth=True
    ))

    # Add model information
    enhancer.add_model_info("UserResponse", SDKModelInfo(
        class_name="User",
        description="User account information",
        is_response_model=True,
        platform_specific={
            SDKPlatform.PYTHON: {"base_class": "BaseModel"},
            SDKPlatform.TYPESCRIPT: {"interface": True},
            SDKPlatform.GO: {"struct_tags": "json"},
        }
    ))

    # Add code examples
    examples = create_platform_examples()
    for endpoint_id, endpoint_examples in examples.items():
        for example in endpoint_examples:
            enhancer.add_code_example(endpoint_id, example)

    return enhancer


def export_sdk_spec(app: FastAPI, output_file: str = "openapi-sdk.json") -> None:
    """
    Export enhanced OpenAPI specification optimized for SDK generation.

    Args:
        app: FastAPI application
        output_file: Output file path for the OpenAPI spec
    """
    enhancer = setup_sdk_documentation(app)
    enhanced_spec = enhancer.generate_enhanced_openapi()

    with open(output_file, 'w') as f:
        json.dump(enhanced_spec, f, indent=2, default=str)

    print(f"Enhanced OpenAPI specification exported to {output_file}")


def generate_readme_examples() -> str:
    """Generate README examples for SDK documentation."""
    return """
# Janua SDK Examples

## Installation

### Python
```bash
pip install janua
```

### TypeScript/JavaScript
```bash
npm install @janua/typescript-sdk
```

### Go
```bash
go get github.com/madfam-io/go-sdk
```

## Quick Start

### Authentication

#### Python
```python
from janua import JanuaClient

client = JanuaClient(base_url="https://api.janua.dev")
response = await client.auth.sign_in(
    email="user@example.com",
    password="password"
)
```

#### TypeScript
```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const client = new JanuaClient({
  baseUrl: 'https://api.janua.dev'
});

const response = await client.auth.signIn({
  email: 'user@example.com',
  password: 'password'
});
```

#### Go
```go
import "github.com/madfam-io/go-sdk/client"

client := client.NewJanuaClient(&client.Config{
    BaseURL: "https://api.janua.dev",
})

response, err := client.Auth.SignIn(ctx, &auth.SignInRequest{
    Email:    "user@example.com",
    Password: "password",
})
```

## User Management

### Get Current User
```python
# Python
user = await client.users.get_me()

# TypeScript
const user = await client.users.getMe();

# Go
user, err := client.Users.GetMe(ctx)
```

### Update User Profile
```python
# Python
await client.users.update_me(
    first_name="John",
    last_name="Doe"
)

# TypeScript
await client.users.updateMe({
  firstName: 'John',
  lastName: 'Doe'
});

# Go
_, err := client.Users.UpdateMe(ctx, &users.UpdateMeRequest{
    FirstName: "John",
    LastName:  "Doe",
})
```

## Error Handling

### Python
```python
from janua.exceptions import ValidationError, AuthenticationError

try:
    await client.auth.sign_in(email="invalid", password="wrong")
except ValidationError as e:
    print(f"Validation errors: {e.validation_errors}")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
```

### TypeScript
```typescript
import { ValidationError, AuthenticationError } from '@janua/typescript-sdk';

try {
  await client.auth.signIn({ email: 'invalid', password: 'wrong' });
} catch (error) {
  if (error instanceof ValidationError) {
    console.error('Validation errors:', error.validationErrors);
  } else if (error instanceof AuthenticationError) {
    console.error('Auth failed:', error.message);
  }
}
```

## Configuration

### Python
```python
from janua import JanuaClient, ClientConfig, RetryConfig

config = ClientConfig(
    base_url="https://api.janua.dev",
    timeout=30.0,
    retry_config=RetryConfig(max_retries=3),
    debug=True
)

client = JanuaClient(config)
```

### TypeScript
```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const client = new JanuaClient({
  baseUrl: 'https://api.janua.dev',
  timeout: 30000,
  retryConfig: {
    maxRetries: 3,
    backoffMultiplier: 2.0
  },
  debug: true
});
```
"""