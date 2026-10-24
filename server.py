import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "spotify_refresh_token": "",
        "poll_interval_ms": 5000,
        "idle_poll_interval_ms": 15000,
        "full_refresh_interval_ms": 600000,
        "port": 5050,
    }


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class SpotifyService:
    def __init__(self):
        self.access_token = ""
        self.token_expiration = 0.0
        self.last_track_cache = None
        self.last_fetch_ts = 0.0

    def is_configured(self, cfg):
        return bool(
            cfg.get("spotify_client_id")
            and cfg.get("spotify_client_secret")
            and cfg.get("spotify_refresh_token")
        )

    def refresh_access_token(self, cfg):
        if not self.is_configured(cfg):
            return False, "Missing Spotify credentials"

        data = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": cfg["spotify_refresh_token"],
                "client_id": cfg["spotify_client_id"],
                "client_secret": cfg["spotify_client_secret"],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "SpotifyKindle/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                self.access_token = payload.get("access_token", "")
                expires_in = int(payload.get("expires_in", 3600))
                self.token_expiration = time.time() + max(60, expires_in - 60)
                if payload.get("refresh_token"):
                    cfg["spotify_refresh_token"] = payload["refresh_token"]
                    save_config(cfg)
                return True, ""
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return False, f"Spotify Auth HTTP {e.code}: {err_body}"
        except Exception as e:
            return False, f"Auth Error: {str(e)}"

    def exchange_auth_code(self, cfg, code, redirect_uri):
        data = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": cfg.get("spotify_client_id", ""),
                "client_secret": cfg.get("spotify_client_secret", ""),
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "SpotifyKindle/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                refresh_tok = payload.get("refresh_token", "")
                if refresh_tok:
                    cfg["spotify_refresh_token"] = refresh_tok
                    save_config(cfg)
                    self.access_token = payload.get("access_token", "")
                    expires_in = int(payload.get("expires_in", 3600))
                    self.token_expiration = time.time() + max(60, expires_in - 60)
                    return True, ""
                return False, "No refresh_token returned by Spotify"
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return False, f"Spotify HTTP {e.code}: {err_body}"
        except Exception as e:
            return False, str(e)

    def fetch_currently_playing(self):
        cfg = load_config()
        result = {
            "success": False,
            "configured": self.is_configured(cfg),
            "isPlaying": False,
            "hasTrack": False,
            "title": "",
            "artist": "",
            "album": "",
            "artworkUrl": "",
            "artworkUrlSmall": "",
            "progressMs": 0,
            "durationMs": 0,
            "httpCode": 0,
            "errorMessage": "",
            "serverTimestampMs": int(time.time() * 1000),
        }

        if not result["configured"]:
            result["errorMessage"] = "Spotify Not Configured"
            return result

        if not self.access_token or time.time() >= self.token_expiration:
            ok, err = self.refresh_access_token(cfg)
            if not ok:
                result["errorMessage"] = err or "Auth Token Failed"
                return result

        req = urllib.request.Request(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "SpotifyKindle/1.0",
            },
            method="GET",
        )

        req_start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                code = resp.getcode()
                result["httpCode"] = code
                if code == 204:
                    result["success"] = True
                    result["hasTrack"] = False
                    result["isPlaying"] = False
                    result["errorMessage"] = "Player Idle"
                    return result

                raw = resp.read().decode("utf-8")
                doc = json.loads(raw) if raw else {}
                result["success"] = True
                result["isPlaying"] = bool(doc.get("is_playing", False))
                progress_ms = int(doc.get("progress_ms") or 0)
                if result["isPlaying"]:
                    elapsed_ms = int((time.time() - req_start) * 1000)
                    progress_ms += elapsed_ms
                result["progressMs"] = progress_ms

                item = doc.get("item")
                if item:
                    result["hasTrack"] = True
                    result["title"] = item.get("name") or "Unknown Title"
                    result["durationMs"] = int(item.get("duration_ms") or 0)
                    if (
                        result["durationMs"] > 0
                        and result["progressMs"] > result["durationMs"]
                    ):
                        result["progressMs"] = result["durationMs"]

                    artists = item.get("artists") or []
                    result["artist"] = ", ".join(
                        [a.get("name", "") for a in artists if a.get("name")]
                    ) or "Unknown Artist"

                    album = item.get("album") or {}
                    result["album"] = album.get("name") or ""
                    images = album.get("images") or []
                    if images:
                        # Medium/High res (300px or 640px) for Kindle high-DPI display, plus smallest (64px) for classic SpotifyThing mode
                        sorted_imgs = sorted(
                            images, key=lambda x: x.get("width") or 9999
                        )
                        result["artworkUrlSmall"] = sorted_imgs[0].get("url", "")
                        # Prefer ~300px image if available, else largest
                        med_img = next(
                            (img for img in sorted_imgs if (img.get("width") or 0) >= 250),
                            sorted_imgs[-1],
                        )
                        result["artworkUrl"] = med_img.get("url", "")
                else:
                    result["hasTrack"] = False
                    result["errorMessage"] = "No Track Details"
                return result

        except urllib.error.HTTPError as e:
            result["httpCode"] = e.code
            if e.code == 401:
                self.access_token = ""
                ok, _ = self.refresh_access_token(cfg)
                if ok:
                    return self.fetch_currently_playing()
                result["errorMessage"] = "401 Unauthorized"
            elif e.code == 429:
                result["errorMessage"] = "Rate Limited (429)"
            else:
                result["errorMessage"] = f"HTTP Error {e.code}"
            return result
        except Exception as e:
            result["errorMessage"] = f"Network Error: {str(e)}"
            return result

    def control_playback(self, command):
        """Sends playback commands: 'next', 'previous', 'play', 'pause', 'toggle'."""
        cfg = load_config()
        if not self.is_configured(cfg):
            return False, "Spotify Not Configured", None

        if not self.access_token or time.time() >= self.token_expiration:
            ok, err = self.refresh_access_token(cfg)
            if not ok:
                return False, err or "Auth Token Failed", None

        cmd = (command or "").strip().lower()
        if cmd == "toggle":
            current = self.fetch_currently_playing()
            cmd = "pause" if current.get("isPlaying") else "play"

        endpoints = {
            "next": ("POST", "https://api.spotify.com/v1/me/player/next"),
            "previous": ("POST", "https://api.spotify.com/v1/me/player/previous"),
            "play": ("PUT", "https://api.spotify.com/v1/me/player/play"),
            "pause": ("PUT", "https://api.spotify.com/v1/me/player/pause"),
        }

        if cmd not in endpoints:
            return (
                False,
                f"Unknown command '{command}' (use next, previous, play, pause, toggle)",
                None,
            )

        method, url = endpoints[cmd]
        req = urllib.request.Request(
            url,
            data=b"",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "User-Agent": "SpotifyKindle/1.0",
                "Content-Length": "0",
            },
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                time.sleep(0.35)
                updated = self.fetch_currently_playing()
                return True, f"Command '{cmd}' executed successfully", updated
        except urllib.error.HTTPError as e:
            raw_err = e.read().decode("utf-8", errors="replace")
            err_msg = ""
            try:
                err_json = json.loads(raw_err)
                err_msg = err_json.get("error", {}).get("message", "")
            except Exception:
                err_msg = raw_err

            if e.code == 404:
                return (
                    False,
                    "No active Spotify player found. Start music on your phone or PC first.",
                    None,
                )
            elif e.code in (401, 403):
                if "Permissions missing" in err_msg or "scope" in err_msg.lower():
                    return (
                        False,
                        "Playback permission missing. Re-link Spotify at /auth to grant playback controls.",
                        None,
                    )
                if "Restriction violated" in err_msg or "PREMIUM_REQUIRED" in err_msg:
                    return False, f"Spotify restriction: {err_msg}", None
                if e.code == 401:
                    self.access_token = ""
                    ok, _ = self.refresh_access_token(cfg)
                    if ok:
                        return self.control_playback(cmd)
                return False, f"Spotify Auth {e.code}: {err_msg}", None
            return False, f"Spotify HTTP {e.code}: {err_msg}", None
        except Exception as e:
            return False, f"Playback error: {str(e)}", None


spotify_service = SpotifyService()


def extract_code_from_input(raw_input):
    raw_input = raw_input.strip()
    if "code=" in raw_input:
        sub = raw_input.split("code=", 1)[1]
        sub = sub.split("&", 1)[0].split("#", 1)[0].strip()
        return sub
    return raw_input


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class RequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Clean concise logging
        if not self.path.startswith("/api/now-playing"):
            print(f"[Server] {self.address_string()} - {fmt % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html_str, status=200):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/simulator":
            self.serve_static_file("simulator.html", "text/html; charset=utf-8")
            return

        if path == "/kindle":
            self.serve_static_file("kindle.html", "text/html; charset=utf-8")
            return

        if path == "/api/now-playing":
            data = spotify_service.fetch_currently_playing()
            cfg = load_config()
            data["lanIp"] = get_lan_ip()
            data["port"] = cfg.get("port", 5050)
            self.send_json(data)
            return

        if path == "/api/player/command":
            cmd = query.get("action", ["toggle"])[0]
            ok, msg, updated = spotify_service.control_playback(cmd)
            self.send_json(
                {"success": ok, "command": cmd, "message": msg, "playback": updated}
            )
            return

        if path == "/api/info":
            cfg = load_config()
            self.send_json(
                {
                    "lanIp": get_lan_ip(),
                    "port": cfg.get("port", 5050),
                    "configured": spotify_service.is_configured(cfg),
                    "clientId": cfg.get("spotify_client_id", ""),
                }
            )
            return

        if path == "/api/artwork":
            img_url = query.get("url", [""])[0]
            if not img_url or not (
                img_url.startswith("https://") or img_url.startswith("http://")
            ):
                self.send_error(400, "Invalid artwork url")
                return
            try:
                req = urllib.request.Request(
                    img_url, headers={"User-Agent": "SpotifyKindle/1.0"}
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    img_bytes = resp.read()
                    ctype = resp.headers.get("Content-Type", "image/jpeg")
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(img_bytes)))
                    self.end_headers()
                    self.wfile.write(img_bytes)
            except Exception as e:
                self.send_error(502, f"Artwork fetch failed: {e}")
            return

        if path == "/auth":
            self.serve_auth_portal()
            return

        if path == "/callback":
            code = query.get("code", [""])[0]
            if not code:
                self.serve_auth_portal("No authorization code received from Spotify.")
                return
            cfg = load_config()
            host = self.headers.get("Host", f"127.0.0.1:{cfg.get('port', 5050)}")
            redirect_uri = f"http://{host}/callback"
            ok, err = spotify_service.exchange_auth_code(cfg, code, redirect_uri)
            if ok:
                self.send_html(
                    "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#121212;color:#1DB954;text-align:center;padding:40px;'>"
                    "<h2>&#10003; Spotify Account Linked!</h2>"
                    "<p style='color:#fff;'>Your Kindle display & simulator are now connected.</p>"
                    "<p><a href='/' style='color:#1DB954;'>Return to Simulator</a></p></body></html>"
                )
            else:
                self.serve_auth_portal(err)
            return

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            self.serve_static_file(rel)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/player/command":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {}
            query = urllib.parse.parse_qs(parsed.query)
            cmd = body.get("command") or query.get("action", ["toggle"])[0]
            ok, msg, updated = spotify_service.control_playback(cmd)
            self.send_json(
                {"success": ok, "command": cmd, "message": msg, "playback": updated}
            )
            return

        if parsed.path == "/exchange":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            raw_input = params.get("code_input", [""])[0]
            redirect_uri = params.get(
                "redirect_uri", ["http://127.0.0.1:8888/callback"]
            )[0]
            code = extract_code_from_input(raw_input)
            cfg = load_config()
            ok, err = spotify_service.exchange_auth_code(cfg, code, redirect_uri)
            if ok:
                self.send_html(
                    "<!DOCTYPE html><html><body style='font-family:sans-serif;background:#121212;color:#1DB954;text-align:center;padding:40px;'>"
                    "<h2>&#10003; Spotify Account Linked!</h2>"
                    "<p style='color:#fff;'>Refresh token saved to config.json.</p>"
                    "<p><a href='/' style='color:#1DB954;font-weight:bold;'>Back to Kindle Simulator</a></p></body></html>"
                )
            else:
                self.serve_auth_portal(err)
            return

        self.send_error(404, "Not Found")

    def serve_static_file(self, rel_path, content_type=None):
        safe_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if not safe_path.startswith(STATIC_DIR) or not os.path.isfile(safe_path):
            self.send_error(404, "File not found")
            return

        if not content_type:
            if safe_path.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif safe_path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif safe_path.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            elif safe_path.endswith(".png"):
                content_type = "image/png"
            else:
                content_type = "application/octet-stream"

        with open(safe_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_auth_portal(self, last_error=""):
        cfg = load_config()
        client_id = cfg.get("spotify_client_id", "")
        local_loopback_uri = "http://127.0.0.1:8888/callback"
        auth_url_loopback = (
            "https://accounts.spotify.com/authorize?"
            + urllib.parse.urlencode(
                {
                    "client_id": client_id,
                    "response_type": "code",
                    "redirect_uri": local_loopback_uri,
                    "scope": "user-read-currently-playing user-read-playback-state user-modify-playback-state",
                }
            )
        )
        err_html = f"<div class='err'>{last_error}</div>" if last_error else ""
        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Link Spotify - SpotifyKindle</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#121212;color:#fff;margin:0;padding:20px;display:flex;justify-content:center;}}
.card{{max-width:460px;width:100%;background:#181818;border-radius:12px;padding:24px;box-sizing:border-box;box-shadow:0 8px 24px rgba(0,0,0,0.5);}}
h2{{margin:0 0 8px;color:#1DB954;}}
p{{font-size:14px;line-height:1.5;color:#b3b3b3;margin:8px 0 16px;}}
.btn{{display:block;width:100%;background:#1DB954;color:#000;font-weight:700;text-align:center;padding:14px;border-radius:24px;text-decoration:none;border:none;font-size:15px;cursor:pointer;box-sizing:border-box;margin:10px 0;}}
.btn-sec{{background:#282828;color:#fff;font-weight:600;}}
input[type=text]{{width:100%;padding:12px;border-radius:8px;border:1px solid #333;background:#222;color:#fff;box-sizing:border-box;font-size:13px;margin:8px 0;}}
.err{{background:#4a151b;border-left:4px solid #e91429;padding:10px;border-radius:4px;font-size:13px;color:#ffb3b8;margin-bottom:14px;word-break:break-word;}}
code{{background:#282828;padding:2px 6px;border-radius:4px;color:#1DB954;font-size:12px;word-break:break-all;}}
</style></head><body><div class='card'>
<h2>Link Your Spotify (SpotifyKindle)</h2>
<p>Connect your Spotify account so the Kindle E-Ink display can show your currently playing track and album artwork.</p>
{err_html}
<a class='btn btn-sec' href='{auth_url_loopback}' target='_blank'>1. Open Spotify Login</a>
<form method='POST' action='/exchange'>
<p style='font-size:12px;margin:6px 0;'>2. After clicking Agree, copy the full URL from your browser's address bar (starting with <code>http://127.0.0.1:8888/callback?code=...</code>) and paste it below:</p>
<input type='text' name='code_input' placeholder='Paste redirected URL or code here...' required>
<input type='hidden' name='redirect_uri' value='{local_loopback_uri}'>
<button type='submit' class='btn'>3. Complete Link</button>
</form>
<p style='text-align:center;margin-top:16px;'><a href='/' style='color:#b3b3b3;font-size:13px;'>&larr; Back to Simulator</a></p>
</div></body></html>"""
        self.send_html(html)


def main():
    cfg = load_config()
    port = int(cfg.get("port", 5050))
    lan_ip = get_lan_ip()
    server = ThreadedHTTPServer(("0.0.0.0", port), RequestHandler)
    print("=" * 62)
    print("  SpotifyKindle - Live Desktop E-Ink Simulator & Kindle Server")
    print("=" * 62)
    print(f"  Desktop Simulator (PC):   http://localhost:{port}/")
    print(f"  Kindle Web View (E-Ink):  http://{lan_ip}:{port}/kindle")
    print(f"  Spotify OAuth Setup:      http://localhost:{port}/auth")
    print("=" * 62)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    import runpy
    parent_server = os.path.join(os.path.dirname(BASE_DIR), "server.py")
    if os.path.exists(parent_server):
        runpy.run_path(parent_server, run_name="__main__")
    else:
        main()
