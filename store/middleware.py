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
        # 1. Continue normal request execution first so the visitor gets their page immediately
        response = self.get_response(request)

        # 2. If NetWatch URL or API key is not configured, skip forwarding silently
        if not self.api_url or not self.api_key:
            return response

        # 3. Path Filter: exclude static files, media, and admin database updates to reduce noise
        ignored_prefixes = [
            '/static/',
            '/media/',
            '/admin/',
        ]
        is_ignored = any(request.path.startswith(prefix) for prefix in ignored_prefixes)

        if not is_ignored:
            # 4. Extract IP address: check for simulated IP (from test tools) first, then fallback to REMOTE_ADDR
            # Check custom simulator headers first
            ip = request.META.get('HTTP_X_NETWATCH_SIMULATED_IP')
            if not ip:
                ip = request.META.get('HTTP_X_FORWARDED_FOR')
                if ip:
                    # Take the first IP if there is a list of proxies
                    ip = ip.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

            # 5. Extract other request metadata
            url_accessed = request.path
            request_method = request.method

            # 6. Spin up a background thread to forward the log
            # This makes the API call fire-and-forget, keeping page responses instant.
            thread = threading.Thread(
                target=self.forward_to_netwatch,
                args=(ip, url_accessed, request_method),
                daemon=True  # Daemonized thread will close automatically when the server stops
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
