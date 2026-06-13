"""Download-client adapters for prowlarr-media.

Stdlib-only. Two clients:

  QbtClient  — qBittorrent WebUI API v2 (torrents)
  SabClient  — SABnzbd HTTP API; supports real SABnzbd (api_key auth) and
               RDT-Client's SAB-emulation (ASP.NET cookie login)

Both are constructed from the parsed config dicts produced by _config.py.
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.parse
import urllib.request


# ── qBittorrent ───────────────────────────────────────────────────────────

class QbtClient:
    def __init__(self, conf: dict):
        self.url = conf["url"].rstrip("/")
        self.username = conf.get("username", "")
        self.password = conf.get("password", "")
        self._opener: urllib.request.OpenerDirector | None = None

    def _session(self) -> urllib.request.OpenerDirector:
        if self._opener is not None:
            return self._opener
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        data = urllib.parse.urlencode(
            {"username": self.username, "password": self.password}
        ).encode()
        opener.open(
            urllib.request.Request(
                f"{self.url}/api/v2/auth/login",
                data=data,
                headers={"Referer": self.url},
            ),
            timeout=15,
        )
        self._opener = opener
        return opener

    def add(self, torrent_bytes: bytes, save_path: str, category: str) -> None:
        opener = self._session()
        boundary = "----prowlarrMedia"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="torrents"; filename="grab.torrent"\r\n'
            f"Content-Type: application/x-bittorrent\r\n\r\n"
        ).encode() + torrent_bytes + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="savepath"\r\n\r\n{save_path}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="category"\r\n\r\n{category}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="autoTMM"\r\n\r\nfalse\r\n'
            f"--{boundary}--\r\n"
        ).encode()
        req = urllib.request.Request(
            f"{self.url}/api/v2/torrents/add",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Referer": self.url,
            },
        )
        with opener.open(req, timeout=30) as r:
            resp = r.read().decode().strip()
        if resp != "Ok.":
            raise RuntimeError(f"qBittorrent rejected the torrent: {resp!r}")

    def info(self, category: str | None = None, hashes: str | None = None) -> list[dict]:
        opener = self._session()
        params = {}
        if category:
            params["category"] = category
        if hashes:
            params["hashes"] = hashes
        qs = ("?" + urllib.parse.urlencode(params)) if params else ""
        with opener.open(f"{self.url}/api/v2/torrents/info{qs}", timeout=15) as r:
            return json.loads(r.read())

    def recheck(self, hashes: str) -> None:
        opener = self._session()
        data = urllib.parse.urlencode({"hashes": hashes}).encode()
        opener.open(
            urllib.request.Request(f"{self.url}/api/v2/torrents/recheck", data=data),
            timeout=15,
        )


# ── SABnzbd / RDT-Client ────────────────────────────────────────────────────

class SabClient:
    def __init__(self, conf: dict):
        self.url = conf["url"].rstrip("/")
        self.impl = conf.get("impl", "sabnzbd")
        self.api_key = conf.get("api_key", "")
        self.username = conf.get("username", "")
        self.password = conf.get("password", "")
        self._opener: urllib.request.OpenerDirector | None = None

    def _session(self) -> urllib.request.OpenerDirector:
        if self._opener is not None:
            return self._opener
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        if self.impl == "rdt-client":
            # RDT-Client wants an ASP.NET cookie from a JSON login POST.
            opener.open(
                urllib.request.Request(
                    f"{self.url}/Api/Authentication/Login",
                    data=json.dumps(
                        {"UserName": self.username, "Password": self.password}
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=15,
            )
        self._opener = opener
        return opener

    def _api(self, params: dict, method: str = "GET") -> dict:
        opener = self._session()
        q = dict(params)
        q.setdefault("output", "json")
        if self.impl == "sabnzbd" and self.api_key:
            q["apikey"] = self.api_key
        url = f"{self.url}/api?{urllib.parse.urlencode(q)}"
        with opener.open(urllib.request.Request(url, method=method), timeout=30) as r:
            return json.loads(r.read())

    def addurl(self, nzb_url: str, category: str, priority: str = "-100") -> str:
        resp = self._api(
            {"mode": "addurl", "name": nzb_url, "cat": category, "priority": priority},
            method="POST",
        )
        if not resp.get("status") or not resp.get("nzo_ids"):
            raise RuntimeError(f"Usenet client rejected the NZB: {resp}")
        return resp["nzo_ids"][0]

    def queue(self) -> list[dict]:
        # RDT-Client exposes a richer native endpoint; fall back to SAB queue.
        if self.impl == "rdt-client":
            opener = self._session()
            with opener.open(f"{self.url}/Api/Torrents", timeout=15) as r:
                return json.loads(r.read())
        resp = self._api({"mode": "queue"})
        return resp.get("queue", {}).get("slots", [])
