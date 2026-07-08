import logging
import threading
import requests
from django.conf import settings

logger = logging.getLogger('shopsafe.audit')

def log_event(request, event_type, username=None, details=None):
    """
    Records an audit log event locally and forwards it asynchronously in the background
    to NetWatch's security event ingestion REST API.
    """
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')

    # 1. Log locally to ShopSafe logs
    logger.info(
        f"ShopSafe Security Event: {event_type.upper()} | IP: {ip} | User: {username} | Details: {details}"
    )

    # 2. Asynchronously forward to NetWatch Event Ingest API
    api_url = getattr(settings, 'NETWATCH_EVENTS_API_URL', None)
    api_key = getattr(settings, 'NETWATCH_API_KEY', None)

    if api_url and api_key:
        payload = {
            'ip_address': ip,
            'event_type': event_type,
            'username': username or 'anonymous',
            'details': details or '',
            'user_agent': user_agent,
            'source': 'shopsafe'
        }
        
        # Fire-and-forget in a background thread to prevent latency
        thread = threading.Thread(
            target=send_event_to_netwatch,
            args=(api_url, api_key, payload),
            daemon=True
        )
        thread.start()


def get_client_ip(request):
    """Safely extracts client IP address checking custom simulator headers."""
    ip = request.META.get('HTTP_X_NETWATCH_SIMULATED_IP')
    if not ip:
        ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip:
            ip = ip.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def send_event_to_netwatch(api_url, api_key, payload):
    """Performs HTTP POST log forwarding to NetWatch."""
    headers = {
        'Authorization': f'Api-Key {api_key}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=3)
        if response.status_code != 201:
            logger.error(
                f"NetWatch Event Ingest failed. Status: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.warning(
            f"NetWatch Event Ingest connection failed. Server might be offline. Error: {e}"
        )
