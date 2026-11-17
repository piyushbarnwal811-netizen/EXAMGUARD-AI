import ipaddress

from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        candidates = [
            item.strip().strip("[]")
            for item in forwarded_for.split(",")
            if item.strip()
        ]
        if candidates:
            return candidates[0]

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip().strip("[]")

    if request.client:
        return request.client.host

    return "0.0.0.0"


def is_ip_allowed(client_ip: str | None, allowed_ranges: str | None) -> bool:
    if not client_ip or not allowed_ranges:
        return False

    try:
        ip = ipaddress.ip_address(str(client_ip).strip().strip("[]"))
    except (TypeError, ValueError):
        return False

    if not isinstance(allowed_ranges, str):
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
        except (TypeError, ValueError):
            continue

    return False
