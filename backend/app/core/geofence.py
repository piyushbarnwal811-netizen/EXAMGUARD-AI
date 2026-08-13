import ipaddress

from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "0.0.0.0"


def is_ip_allowed(client_ip: str, allowed_ranges: str) -> bool:
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    networks = [
        item.strip()
        for item in allowed_ranges.split(",")
        if item.strip()
    ]

    for network in networks:
        try:
            if ip in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue

    return False
