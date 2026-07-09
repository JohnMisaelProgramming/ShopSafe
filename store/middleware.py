"""
ShopSafe Request Forwarding Middleware
======================================
This middleware intercepts every request hitting the ShopSafe application,
extracts the request details, and forwards them asynchronously (non-blocking)
to the NetWatch Ingest API.

Architecture:
    Client Request  →  ShopSafe Middleware  →  (Spawns background thread)
                                                     │
                                                     ▼
                                            POST http://localhost:8000/api/ingest/

Why Asynchronous:
    Sending HTTP requests is slow (network I/O latency). If we forwarded the logs
    synchronously, every page load on ShopSafe would be delayed by 50ms-200ms.
    By using Python's threading library, the forwarding happens in the background,
    leaving the visitor's page load time completely unaffected.

Why it ignores certain paths:
    Just like in NetWatch, we don't want to log static files (CSS, JS, images)
    or admin dashboard actions to prevent polluting the logs with false-positives
    or noise.
"""

import logging
import threading
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NetWatchForwardingMiddleware:
    """
    Middleware that captures client request data and forwards it to NetWatch.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        
        # Load API configurations from settings
        self.api_url = getattr(settings, 'NETWATCH_API_URL', None)
        self.api_key = getattr(settings, 'NETWATCH_API_KEY', None)

    def __call__(self, request):
        # 1. Extract real client IP (supporting reverse proxies like Nginx/Cloudflare)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Direct socket connection
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            # Trust simulated IP ONLY for direct local loopback calls (no proxies)
            if ip in ('127.0.0.1', '::1'):
                simulated_ip = request.META.get('HTTP_X_NETWATCH_SIMULATED_IP')
                if simulated_ip:
                    ip = simulated_ip

        # 2. Whitelist Check (with 5-minute memory cache backer)
        from django.core.cache import cache
        cache_whitelist_key = f"whitelisted_ip:{ip}"
        is_whitelisted = cache.get(cache_whitelist_key)
        
        if is_whitelisted is None:
            is_whitelisted = False
            if ip in ('127.0.0.1', '::1'):
                is_whitelisted = True
            else:
                import os
                import sqlite3
                netwatch_db_path = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'NetWatch', 'db.sqlite3'))
                if os.path.exists(netwatch_db_path):
                    try:
                        conn = sqlite3.connect(netwatch_db_path, timeout=5)
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM alerts_ipwhitelist WHERE ip_address = ?", (ip,))
                        if cursor.fetchone():
                            is_whitelisted = True
                        conn.close()
                    except Exception:
                        pass
                else:
                    # Deployed Cloud Production: Query the NetWatch check-block HTTP API
                    if self.api_url and self.api_key:
                        try:
                            check_url = self.api_url.replace('/api/ingest/', '/api/check-block/')
                            headers = {'Authorization': f'Api-Key {self.api_key}'}
                            resp = requests.get(check_url, params={'ip': ip}, headers=headers, timeout=2)
                            if resp.status_code == 200:
                                data = resp.json()
                                is_whitelisted = data.get('whitelisted', False)
                        except Exception:
                            pass
            cache.set(cache_whitelist_key, is_whitelisted, timeout=300)

        # 3. Blocklist Check (with 5-minute memory cache backer)
        is_blocked = False
        if not is_whitelisted:
            cache_block_key = f"blocked_ip:{ip}"
            is_blocked = cache.get(cache_block_key)
            
            if is_blocked is None:
                is_blocked = False
                import os
                import sqlite3
                netwatch_db_path = os.path.abspath(os.path.join(settings.BASE_DIR, '..', 'NetWatch', 'db.sqlite3'))
                if os.path.exists(netwatch_db_path):
                    try:
                        conn = sqlite3.connect(netwatch_db_path, timeout=5)
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM alerts_ipblocklist WHERE ip_address = ?", (ip,))
                        if cursor.fetchone():
                            is_blocked = True
                        conn.close()
                    except Exception:
                        pass
                else:
                    # Deployed Cloud Production: Query the NetWatch check-block HTTP API
                    if self.api_url and self.api_key:
                        try:
                            check_url = self.api_url.replace('/api/ingest/', '/api/check-block/')
                            headers = {'Authorization': f'Api-Key {self.api_key}'}
                            resp = requests.get(check_url, params={'ip': ip}, headers=headers, timeout=2)
                            if resp.status_code == 200:
                                data = resp.json()
                                is_blocked = data.get('blocked', False)
                                if data.get('whitelisted'):
                                    cache.set(f"whitelisted_ip:{ip}", True, timeout=300)
                        except Exception:
                            pass
                cache.set(cache_block_key, is_blocked, timeout=300)

        if is_blocked:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden(
                "<h1>403 Forbidden</h1><p>Access Denied: Your IP address has been blocked by NetWatch Security Center.</p>"
            )

        # 4. Continue normal request execution
        response = self.get_response(request)

        # 5. If NetWatch URL or API key is not configured, skip forwarding silently
        if not self.api_url or not self.api_key:
            return response

        # 6. Path Filter: exclude static files, media, and admin database updates to reduce noise
        ignored_prefixes = [
            '/static/',
            '/media/',
            '/admin/',
        ]
        is_ignored = any(request.path.startswith(prefix) for prefix in ignored_prefixes)

        if not is_ignored:
            url_accessed = request.path
            request_method = request.method

            # 7. Spin up a background thread to forward the log
            # This makes the API call fire-and-forget, keeping page responses instant.
            thread = threading.Thread(
                target=self.forward_to_netwatch,
                args=(ip, url_accessed, request_method),
                daemon=True
            )
            thread.start()

        return response

    def forward_to_netwatch(self, ip, url_accessed, request_method):
        """
        Sends the request metadata via HTTP POST to the NetWatch ingest API.
        This runs entirely within a background thread.
        """
        payload = {
            'ip_address': ip,
            'url_accessed': url_accessed,
            'request_method': request_method,
            'source': 'shopsafe'
        }
        
        headers = {
            'Authorization': f'Api-Key {self.api_key}',
            'Content-Type': 'application/json'
        }

        try:
            # Send the request with a short timeout to prevent thread leak if NetWatch goes offline
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=3)
            
            if response.status_code != 201:
                logger.error(
                    "NetWatch Ingest: failed to log request. Status: %d, Response: %s",
                    response.status_code, response.text
                )
        except requests.RequestException as e:
            # Handle connection timeouts, DNS failures, or offline NetWatch server gracefully
            logger.warning(
                "NetWatch Ingest: connection failed. NetWatch server might be offline. Error: %s",
                str(e)
            )


class SecurityHeadersMiddleware:
    """
    Middleware that adds HTTP Security Headers to prevent web attacks:
    - Content-Security-Policy (CSP)
    - X-Frame-Options (Clickjacking)
    - X-Content-Type-Options (Mime sniffing)
    - Referrer-Policy
    - HSTS (Force HTTPS in production)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Clickjacking defense
        response['X-Frame-Options'] = 'DENY'
        
        # Mime sniffing defense
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'same-origin'
        
        # XSS Protection for older browsers
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy (CSP)
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://www.google.com https://www.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://www.gstatic.com; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
            "img-src 'self' data: https://images.unsplash.com https://www.google.com https://www.gstatic.com; "
            "frame-src 'self' https://www.google.com; "
            "connect-src 'self' https://www.google.com;"
        )

        # Force HTTPS via HSTS when DEBUG = False
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            
        return response


import time
import requests
import json
from django.utils import timezone

_thread_locals = threading.local()

def timing_wrapper(execute, sql, params, many, context):
    start = time.perf_counter()
    try:
        return execute(sql, params, many, context)
    finally:
        duration = (time.perf_counter() - start) * 1000  # ms
        if not hasattr(_thread_locals, 'query_count'):
            _thread_locals.query_count = 0
            _thread_locals.query_time = 0.0
        _thread_locals.query_count += 1
        _thread_locals.query_time += duration


class PerformanceTelemetryMiddleware:
    """
    Middleware that records response time, DB query counts, and DB execution times
    for major storefront and API endpoints, forwarding them asynchronously to NetWatch.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_url = 'http://127.0.0.1:8000/api/events/'
        self.api_key = getattr(settings, 'NETWATCH_API_KEY', 'nw-capstone-2026-secret-key')

    def __call__(self, request):
        _thread_locals.query_count = 0
        _thread_locals.query_time = 0.0
        
        start_time = time.perf_counter()
        
        from django.db import connection
        with connection.execute_wrapper(timing_wrapper):
            response = self.get_response(request)
            
        end_time = time.perf_counter()
        
        response_time = (end_time - start_time) * 1000  # ms
        db_queries = getattr(_thread_locals, 'query_count', 0)
        db_time = getattr(_thread_locals, 'query_time', 0.0)

        ignored_prefixes = ['/static/', '/media/', '/admin/']
        is_ignored = any(request.path.startswith(prefix) for prefix in ignored_prefixes)

        if not is_ignored:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
                if ip in ('127.0.0.1', '::1'):
                    simulated_ip = request.META.get('HTTP_X_NETWATCH_SIMULATED_IP')
                    if simulated_ip:
                        ip = simulated_ip

            details = {
                'endpoint_url': request.path,
                'response_time_ms': round(response_time, 2),
                'db_query_count': db_queries,
                'db_query_time_ms': round(db_time, 2),
                'status_code': response.status_code,
                'request_method': request.method,
                'timestamp': timezone.now().isoformat()
            }
            
            thread = threading.Thread(
                target=self.forward_telemetry,
                args=(ip, request.user.username if request.user.is_authenticated else 'anonymous', details),
                daemon=True
            )
            thread.start()

        return response

    def forward_telemetry(self, ip, username, details):
        payload = {
            'ip_address': ip,
            'event_type': 'performance_telemetry',
            'username': username,
            'details': json.dumps(details),
            'user_agent': 'ShopSafe Core Engine',
            'source': 'shopsafe'
        }
        
        headers = {
            'Authorization': f'Api-Key {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            requests.post(self.api_url, json=payload, headers=headers, timeout=3)
        except requests.RequestException:
            pass

