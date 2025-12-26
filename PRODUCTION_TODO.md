# Production Improvements TODO

## ✅ Completed Cleanup
- Organized directory structure (src/, tests/, scripts/)
- Removed unnecessary deployment files (Docker, Fly.io, Heroku)
- Updated .gitignore for production
- Consolidated documentation
- No sensitive data in codebase

## 🔧 Code Quality Improvements Needed

### 1. Security Hardening (High Priority)
- [ ] Remove hardcoded JWT_SECRET default
- [ ] Add environment variable validation on startup
- [ ] Implement rate limiting (e.g., 100 requests/minute per IP)
- [ ] Add request size limits (e.g., 1MB max)
- [ ] Use cryptographically secure random for tokens
- [ ] Add CORS configuration for production domains only

### 2. Code Organization (Medium Priority)
- [ ] Split oura_tool.py into modules:
  - `oauth_server.py` - OAuth endpoints
  - `mcp_server.py` - MCP endpoints  
  - `models.py` - Pydantic models
  - `auth.py` - Authentication logic
  - `oura_client.py` - Oura API client
- [ ] Add comprehensive type hints
- [ ] Add docstrings to all functions
- [ ] Create configuration module for settings

### 3. Error Handling (Medium Priority)
- [ ] Create custom exception classes
- [ ] Implement structured error responses
- [ ] Add retry logic for Oura API calls
- [ ] Better error messages for users

### 4. Testing (High Priority)
- [ ] Add unit tests for OAuth flows
- [ ] Add unit tests for MCP handlers
- [ ] Mock Oura API responses
- [ ] Add GitHub Actions CI/CD
- [ ] Code coverage > 80%

### 5. Monitoring & Logging (Low Priority)
- [ ] Replace print() with proper logging
- [ ] Add structured logging (JSON format)
- [ ] Never log sensitive data (tokens, etc.)
- [ ] Add metrics endpoint
- [ ] Add request ID tracking

### 6. Performance (Low Priority)
- [ ] Use connection pooling for HTTP client
- [ ] Add caching for Oura API responses (5 min TTL)
- [ ] Optimize token storage (consider Redis)
- [ ] Add database for production token storage

### 7. Documentation
- [ ] Add API documentation (OpenAPI/Swagger)
- [ ] Document all environment variables
- [ ] Add architecture diagram
- [ ] Create contribution guidelines

## Next Steps

1. Start with security hardening (most critical)
2. Add comprehensive tests
3. Refactor into modules for maintainability
4. Deploy with monitoring