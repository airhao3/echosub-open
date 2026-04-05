import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response
import uuid

logger = logging.getLogger("app.api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Log request details
        start_time = time.time()
        
        # Extract client info
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)
        
        # Get request headers (excluding sensitive info)
        headers = dict(request.headers)
        if "authorization" in headers:
            headers["authorization"] = "[REDACTED]"
        if "cookie" in headers:
            headers["cookie"] = "[REDACTED]"
        
        # Log request start
        logger.info(
            f"REQ-START [{request_id}] {method} {url} from {client_host} "
            f"| Headers: {headers}"
        )
        
        # Process the request
        try:
            # Call the next middleware or endpoint handler
            response = await call_next(request)
            
            # Calculate request processing time
            process_time = time.time() - start_time
            
            # Log response details
            status_code = response.status_code
            logger.info(
                f"REQ-END [{request_id}] {method} {url} | Status: {status_code} "
                f"| Time: {process_time:.3f}s"
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            # Log any exceptions during request processing
            process_time = time.time() - start_time
            logger.error(
                f"REQ-ERROR [{request_id}] {method} {url} | Error: {str(e)} "
                f"| Time: {process_time:.3f}s"
            )
            raise
