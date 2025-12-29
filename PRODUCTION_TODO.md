# Production TODO

## ✅ Completed
- [x] Organized directory structure (src/, tests/, scripts/)
- [x] Removed unnecessary deployment files (Docker, Fly.io, Heroku)
- [x] Updated .gitignore for production
- [x] Consolidated documentation
- [x] No sensitive data in codebase
- [x] Split oura_tool.py into modules
- [x] Add comprehensive type hints
- [x] Add docstrings to all functions
- [x] Add retry logic for Oura API calls
- [x] Better error messages for users
- [x] Implement persistent token storage (SQLite)
- [x] Document all environment variables
- [x] Follow Dreamer schema patterns (outputSchema)

## 🚨 Critical for Production (High Priority)

### Security
- [ ] Remove hardcoded JWT_SECRET default - use env var only
- [ ] Use secrets.token_urlsafe() instead of uuid4 for tokens
- [ ] Add request size limits (1MB max)
- [ ] Validate CORS domains for production (not '*')

### Reliability  
- [ ] Add exponential backoff to retry logic (currently flat retry)
- [ ] Implement comprehensive health check endpoint
- [ ] Add proper logging with context (replace print statements)
- [ ] Handle partial failures gracefully
- [ ] Implement graceful degradation with fallbacks
- [ ] Add resource cleanup in finally blocks

## 📈 Performance & Operations (Medium Priority)

### Performance
- [ ] Implement caching for Oura API responses (5 min TTL)
- [ ] Add connection pooling for HTTP client
- [ ] Implement rate limiting (100 req/min per IP)
- [ ] Limit result sizes (prevent huge responses)
- [ ] Add periodic cache cleanup

### Monitoring
- [ ] Use Python logging module with structured output
- [ ] Add request ID tracking
- [ ] Never log sensitive data (tokens, etc.)
- [ ] Add metrics endpoint for monitoring

## 🧪 Testing & Documentation (Lower Priority)

### Testing
- [ ] Add unit tests for OAuth flows
- [ ] Add unit tests for MCP handlers
- [ ] Mock Oura API responses
- [ ] Add integration tests
- [ ] Set up GitHub Actions CI/CD
- [ ] Test error paths (timeouts, invalid inputs, API failures)
- [ ] Test with MCP Inspector before each deployment

### Documentation
- [ ] Add OpenAPI/Swagger documentation
- [ ] Create architecture diagram
- [ ] Add contribution guidelines

## Next Steps

1. **Immediate** (Do before next deployment):
   - Remove JWT_SECRET default
   - Add exponential backoff
   - Implement proper health check
   
2. **Soon** (Within 1 week):
   - Add caching for Oura API
   - Replace print() with logging
   - Add request size limits

3. **Eventually** (As needed):
   - Comprehensive test suite
   - API documentation
   - Performance monitoring