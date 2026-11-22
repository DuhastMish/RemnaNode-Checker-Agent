"""Пробы: SSH-попытка, проба через прокси и HTTPS-запрос к SNI-домену."""

import ipaddress
import json
import re
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def one_probe(ip):
    try:
        result = subprocess.run(
            [
                "ssh",
                "-vv",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"root@{ip}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT (ssh завис)"
    output = result.stderr
    if "Connection reset by peer" in output:
        return "RESET"
    if "Connection timed out" in output:
        return "TIMEOUT"
    if "Connection refused" in output:
        return "REFUSED"
    if "Authentications that can continue" in output:
        return "SSH OK"
    return "UNKNOWN"


def is_reachable(status):
    return status.startswith("SSH OK") or status.startswith("REFUSED")


def check_ssh(ip, probes=2):
    status = one_probe(ip)
    if is_reachable(status):
        return status
    for _ in range(max(0, probes - 1)):
        status = one_probe(ip)
        if is_reachable(status):
            return status
    return status


def check_proxy(ip, port, probe_url, timeout=8):
    """Возвращает (ok, статус, ms). ok=None — проба не делалась."""
    if not port:
        return None, "no fresh_port", None
    if not probe_url:
        return None, "probe url not set", None
    proxy = f"http://{ip}:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    t0 = time.time()
    try:
        with opener.open(probe_url, timeout=timeout) as resp:
            body = json.load(resp)
        ms = int((time.time() - t0) * 1000)
        if body.get("ok") and body.get("ip") == ip:
            return True, f"PROXY OK {ms}ms", ms
        return False, f"PROXY WRONG IP {body.get('ip')} {ms}ms", ms
    except urllib.error.HTTPError as e:
        return False, f"PROXY HTTP {e.code}", int((time.time() - t0) * 1000)
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        msg = str(e).split("]")[-1].strip()[:40]
        if "timed out" in msg:
            return False, f"PROXY TIMEOUT {ms}ms", ms
        return False, f"PROXY FAIL {msg}", ms


# ---------- SNI-домен: GET https://домен/ → 200 ----------

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
# браузерный User-Agent: часть сайтов отвечает 403 на «python-urllib», и это не недоступность
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def valid_domain(domain):
    """Доменное имя, из которого получается корректная ссылка https://домен/ (не IP, без порта и пути)."""
    if not isinstance(domain, str) or len(domain) > 253:
        return False
    try:
        ipaddress.ip_address(domain)
        return False
    except ValueError:
        pass
    labels = domain.split(".")
    if len(labels) < 2 or labels[-1].isdigit() or not all(_LABEL.match(x) for x in labels):
        return False
    return urllib.parse.urlsplit(f"https://{domain}/").hostname == domain


def check_http(domain, timeout=8):
    """GET https://домен/ с проверкой сертификата; редиректы проходятся. Возвращает (ok, статус, http_code, ms).

    ok — итоговый ответ 200.
    """
    req = urllib.request.Request(f"https://{domain}/", headers={"User-Agent": _UA, "Accept": "*/*"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            resp.read(1024)
            code = resp.status
            redirected = urllib.parse.urlsplit(resp.geturl()).hostname != domain
        ms = int((time.time() - t0) * 1000)
        status = f"HTTP {code}" + (" (редирект на другой домен)" if redirected else "")
        return code == 200, status, code, ms
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}", e.code, int((time.time() - t0) * 1000)
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return False, "TLS: сертификат не прошёл проверку", None, ms
        if isinstance(reason, ssl.SSLError):
            return False, "TLS FAIL", None, ms
        if isinstance(reason, socket.gaierror):
            return False, "DNS FAIL", None, ms
        if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason):
            return False, "TIMEOUT", None, ms
        if isinstance(reason, ConnectionResetError):
            return False, "RESET", None, ms
        if isinstance(reason, ConnectionRefusedError):
            return False, "REFUSED", None, ms
        return False, f"FAIL {str(reason)[:40]}", None, ms
