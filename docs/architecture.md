# chatguru Agent Architecture

## Overview

chatguru Agent is a whitelabel chatbot designed for agentic commerce with RAG capabilities. The React/Vite frontend lives in the `frontend/` directory and communicates with the backend via WebSocket. The architecture is built for maintainability, scalability, and easy customization across different brands and tenants.

## System Architecture

Simple, modular architecture designed for whitelabel deployment:

```mermaid
graph LR
    subgraph "Current Implementation"
        UI[React/Vite Frontend<br/>frontend/] -->|WebSocket /ws| API[FastAPI API]
        API --> AGENT[Agent Service]
        AGENT --> LLM[Azure OpenAI]
        AGENT -->|RAG Tool| PRODUCTDB[Product DB<br/>sqlite-vec]
        AGENT --> LANGFUSE[Langfuse<br/>Tracing]
        API -.-> MINI_UI[Minimal HTML at /<br/>(tests only)]
    end

    subgraph "Future Extensions"
        MCP[MCP Tools<br/>Commerce Platforms]
        AGENT -.-> MCP
    end
```

### Architecture Vision

The system is designed to evolve from a simple chat interface to a full agentic commerce platform:

**Phase 1**: Basic chat with Azure OpenAI ✅
**Phase 2 (Current)**: RAG with sqlite-vec vector database ✅
**Phase 3**: Integrate MCP tools for commerce platforms (PimCore, Strapi, Medusa.js, Stripe)
**Phase 4**: Full agentic commerce with payment processing and order management

## Component Details

### 1. API Layer (FastAPI)

**Purpose**: HTTP API interface and request handling

**Components**:
- **FastAPI Application**: Main web framework
- **CORS Middleware**: Cross-origin resource sharing
- **Health Checks**: Service health monitoring
- **Request/Response Models**: Pydantic validation
- **WebSocket Gateway**: Streaming endpoint at `/ws` (expects `message`, optional `session_id`, and `messages` history array)

**Key Features**:
- Async request handling
- Automatic API documentation (Swagger/OpenAPI)
- Request validation and error handling
- CORS configuration for web clients

### 2. Agent Layer (Direct LangChain)

**Purpose**: Core AI agent logic and conversation management

**Current Implementation**:
- **Agent Service**: Direct LangChain implementation with Azure OpenAI
- **System Prompts**: Configurable prompts for different use cases
- **Message Processing**: Human and system message handling
- **Response Generation**: Direct LLM invocation for responses

**Architecture**:
- **Simplified Design**: Removed LangGraph complexity for MVP
- **Direct Integration**: Azure OpenAI via langchain-openai
- **Future Extensibility**: Ready for LangGraph reintroduction when needed
- **Testing**: Uses GenericFakeChatModel for reliable testing

**Workflow**:
1. **Receive Message**: Accept user input via API
2. **Format Messages**: Create system and human message pair
3. **Generate Response**: Direct LLM call to Azure OpenAI
4. **Return Response**: Send formatted response to client

### 3. Product Database (sqlite-vec)

**Purpose**: Semantic product search with vector embeddings

**Architecture**:
- **Separate Container**: Runs as `product-db` service on port 8001
- **sqlite-vec**: SQLite extension for vector similarity search
- **Azure OpenAI Embeddings**: 1536-dimensional vectors (text-embedding-ada-002)

**Components**:
- `ProductStore`: Core database logic with embedding generation
- `SQLiteProductDatabase`: HTTP client for agent to call the service
- `ProductDatabase`: Abstract interface for future backends (MongoDB)

**Database Schema**:
- `products` table: Product data (id, name, category, brand, price, etc.)
- `product_embeddings` virtual table: Vector embeddings for semantic search

**Data Flow**:
```
Agent → HTTP GET /search?q=... → product-db container → sqlite-vec → Results
```

### 4. External Services

#### Azure OpenAI (Direct Integration)
- **Purpose**: Large Language Model inference
- **Configuration**: Environment-based settings via Pydantic
- **Implementation**: Direct integration via langchain-openai
- **Features**: Azure-specific optimizations, deployment management

#### Langfuse
- **Purpose**: Observability and tracing
- **Features**: Request tracing, performance monitoring, prompt management
- **Integration**: Automatic callback handlers

#### Future MCP Tools
- **Purpose**: Agentic commerce capabilities
- **Integration**: Model Context Protocol for external platform access
- **Examples**: E-commerce platforms, payment systems, inventory management

## Data Flow

### 1. Chat Request Flow

```
React/Vite Frontend (frontend/) → WebSocket /ws → Agent Service → Azure OpenAI → Streamed Tokens
       ↓                              ↓              ↓                ↓
  Sends {message, messages[],     Validation     Direct LLM      Langfuse
        session_id} payloads      & Routing      Call            Tracing
```

### 2. Current Implementation

**Agent Service**:
```python
class Agent:
    def __init__(self) -> None:
        self.agent = AzureChatOpenAI(
            azure_deployment=settings.deployment_name,
            api_key=settings.api_key,
            azure_endpoint=settings.endpoint,
            api_version=settings.api_version,
        )

    def run(self, message: str) -> str:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.strip()),
            HumanMessage(content=message),
        ]
        response = self.agent.invoke(messages)
        return str(response.content)
```

**API Request/Response**:
```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None)

class ChatResponse(BaseModel):
    response: str
    session_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 3. Error Handling

- **API Level**: HTTP status codes and error messages
- **Agent Level**: Graceful degradation and fallback responses
- **External Services**: Retry logic and circuit breakers

## Whitelabel Design Considerations

### 1. Multi-Tenancy Support

**Current Implementation**:
- Environment-based configuration
- Tenant ID in metadata
- Brand name customization

**Future Enhancements**:
- Database-backed tenant configuration
- Per-tenant model selection
- Custom prompt templates
- Tenant-specific RAG sources

### 2. Customization Points

**Brand Customization**:
- Brand name in responses
- Custom system prompts
- Tenant-specific metadata
- Custom error messages

**Behavior Customization**:
- Response style configuration
- Tool availability per tenant
- Rate limiting per tenant
- Feature flags

### 3. Configuration Management

**Environment Variables**:
- Required: Azure OpenAI, Langfuse credentials
- Optional: Brand settings, feature flags
- Development: Debug mode, logging levels

**Future Database Configuration**:
- Tenant-specific settings
- Dynamic configuration updates
- A/B testing capabilities

## Security Considerations

### 1. API Security
- No authentication (development phase)
- CORS configuration
- Input validation and sanitization
- Rate limiting (future)

### 2. Data Privacy
- Session-based conversation storage
- No persistent user data (current)
- Configurable data retention
- GDPR compliance considerations

### 3. External Service Security
- API key management
- Secure credential storage
- Network security (HTTPS)
- Audit logging

## Scalability and Performance

### 1. Horizontal Scaling
- Stateless API design
- Container-based deployment
- Load balancer ready
- Database connection pooling (future)

### 2. Performance Optimization
- Async request handling
- LLM response caching (future)
- Vector search optimization
- Connection pooling

### 3. Monitoring and Observability
- Langfuse tracing integration
- Health check endpoints
- Metrics collection (future)
- Log aggregation

## Extension Points

### 1. Vector Database Integration
- Abstract retriever interface
- Pluggable vector store backends
- Search optimization

### 2. MCP Tool Integration
- Tool registration system
- Dynamic tool loading
- Tool-specific configuration
- Error handling per tool

### 3. Multi-Modal Support
- Image processing capabilities
- Document parsing
- Voice input/output
- Rich media responses

## Development Workflow

### 1. Code Quality
- Pre-commit hooks (ruff, mypy)
- Type checking with mypy
- Code formatting with ruff
- Test coverage requirements

### 2. Testing Strategy
- **Unit Tests**: Agent service with GenericFakeChatModel
- **API Tests**: FastAPI endpoints with mocked dependencies
- **LLM Evaluation**: promptfoo for response quality testing
- **Mocking**: LangChain's fake chat models for reliable testing

### 3. Deployment
- Docker containerization
- Environment-based configuration
- Health checks and monitoring
- Graceful shutdown handling

## Future Architecture Evolution

### Phase 1: MVP ✅
- ✅ Basic chat functionality
- ✅ Azure OpenAI direct integration
- ✅ Langfuse tracing
- ✅ Docker deployment
- ✅ Comprehensive testing with mocks
- ✅ Makefile for development workflow

### Phase 2: RAG Enhancement ✅
- ✅ sqlite-vec vector database
- ✅ Product embeddings with Azure OpenAI
- ✅ Semantic search via RAG tool
- ✅ Separate database container

### Phase 3: Agentic Commerce
- MCP tool integration
- E-commerce platform connections
- Payment processing
- Order management

### Phase 4: Enterprise Features
- Multi-tenancy
- Authentication/authorization
- Advanced monitoring
- Custom model training
