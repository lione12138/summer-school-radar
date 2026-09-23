"""Opt-in native certificate validation for sources with incomplete chains.

No global SSL monkeypatching, unverified requests, or certificate-error retry.
The operating system still validates the hostname and certificate chain.
"""
import ssl

import requests
from requests.adapters import HTTPAdapter
import truststore


class SystemTrustAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **kwargs):
        kwargs['ssl_context'] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return super().proxy_manager_for(proxy, **kwargs)


def get_with_system_trust(url: str, **kwargs) -> requests.Response:
    with requests.Session() as session:
        session.mount('https://', SystemTrustAdapter())
        return session.get(url, **kwargs)
