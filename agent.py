#!/usr/bin/env python3
"""LinkHarbor agent for FiveM / RedM servers (GTA V, Red Dead Redemption 2).

Polls the server's public HTTP endpoints (`/dynamic.json`, `/players.json`,
`/info.json` — every FiveM/RedM server exposes them on its game port, default
30120) and pushes the state to a LinkHarbor "Custom (API)" integration: a
live game-server card on your bio page and push notifications for joins.

    export LH_INGEST_URL="https://dock.at-harbor.com/v1/ingest/123"
    export LH_INGEST_SECRET="…"
    python3 agent.py --host 203.0.113.10 --port 30120 --name "My RP Server" \
        --address "cfx.re/join/abcdef" --url "https://discord.gg/xyz"

No third-party packages needed (Python 3.10+, standard library only).

Events sent (each can drive a push rule in the dashboard):
    server.online    the server answered after being unreachable (or on first run)
    server.offline   the server stopped answering
    player.joined    data.player = name
    player.left      data.player = name
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

log = logging.getLogger("linkharbor")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", required=True, help="server IP / hostname")
    p.add_argument("--port", type=int, default=30120, help="FiveM/RedM HTTP port (default 30120)")
    p.add_argument("--name", default="", help="card title (default: the server's hostname)")
    p.add_argument("--address", default="", help="address shown on the card, e.g. cfx.re/join/abcdef")
    p.add_argument("--url", default="", help="link behind the card's button (Discord, website)")
    p.add_argument("--cta", default="Join server", help="button label")
    p.add_argument("--game", default="", help="game label (default: FiveM or RedM, detected)")
    p.add_argument("--image-url", default="", help="banner image for the large layout")
    p.add_argument("--interval", type=int, default=60, help="seconds between polls (default 60)")
    p.add_argument("--heartbeat", type=int, default=10, help="minutes between state-only updates (0 = only on change)")
    p.add_argument("--no-player-names", action="store_true", help="don't send player names")
    p.add_argument("--ingest-url", default=os.environ.get("LH_INGEST_URL", ""))
    p.add_argument("--ingest-secret", default=os.environ.get("LH_INGEST_SECRET", ""))
    p.add_argument("--once", action="store_true", help="poll once, send, exit")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    if not a.ingest_url or not a.ingest_secret:
        p.error("set LH_INGEST_URL and LH_INGEST_SECRET (or --ingest-url / --ingest-secret)")
    return a


class Ingest:
    def __init__(self, url: str, secret: str) -> None:
        self.url, self.secret = url, secret

    def send(self, event: str | None, data: dict | None, state: dict) -> bool:
        body: dict = {"state": state}
        if event:
            body["event"] = event
            body["event_id"] = f"{event}-{uuid.uuid4()}"
        if data:
            body["data"] = data
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json",
                     "User-Agent": "LinkHarbor-FiveM/1.0"},
        )
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=10) as res:
                    log.debug("← %s %s", res.status, res.read(200).decode(errors="replace"))
                    return True
            except urllib.error.HTTPError as e:
                text = e.read(300).decode(errors="replace")
                if e.code == 401:
                    log.error("401 from LinkHarbor — wrong secret or integration disconnected")
                    return False
                if e.code < 500:
                    log.error("%s from LinkHarbor: %s", e.code, text)
                    return False
                log.warning("%s from LinkHarbor (attempt %d)", e.code, attempt)
            except Exception as e:  # network
                log.warning("request failed (attempt %d): %s", attempt, e)
            time.sleep(2)
        return False


def fetch_json(host: str, port: int, path: str):
    req = urllib.request.Request(f"http://{host}:{port}{path}", headers={"User-Agent": "LinkHarbor-FiveM/1.0"})
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read(512_000).decode(errors="replace"))


def query(host: str, port: int, with_players: bool) -> tuple[dict | None, list[str]]:
    """Returns (info, player names) or (None, []) when the server is unreachable."""
    try:
        dyn = fetch_json(host, port, "/dynamic.json")
    except Exception as e:
        log.debug("dynamic.json failed: %s", e)
        return None, []
    names: list[str] = []
    if with_players:
        try:
            players = fetch_json(host, port, "/players.json")
            names = [str(p.get("name", "")).strip() for p in players if isinstance(p, dict)]
            names = [n for n in names if n]
        except Exception as e:
            log.debug("players.json failed: %s", e)
    info_vars: dict = {}
    try:
        info_vars = fetch_json(host, port, "/info.json").get("vars", {}) or {}
    except Exception as e:
        log.debug("info.json failed: %s", e)
    game = "RedM" if str(info_vars.get("gamename", "")).lower() == "rdr3" else "FiveM"
    return {
        "hostname": strip_colors(str(dyn.get("hostname", "") or info_vars.get("sv_projectName", ""))),
        "map": str(dyn.get("mapname", "") or ""),
        "gametype": str(dyn.get("gametype", "") or ""),
        "players": int(dyn.get("clients", 0) or 0),
        "max_players": int(dyn.get("sv_maxclients", 0) or info_vars.get("sv_maxClients", 0) or 0),
        "game": game,
    }, names


def strip_colors(s: str) -> str:
    """FiveM hostnames carry ^1..^9 colour codes."""
    out, skip = [], False
    for i, ch in enumerate(s):
        if skip:
            skip = False
            continue
        if ch == "^" and i + 1 < len(s) and s[i + 1].isdigit():
            skip = True
            continue
        out.append(ch)
    return "".join(out).strip()


def build_state(a: argparse.Namespace, info: dict | None, names: list[str], last_name: str) -> dict:
    s: dict = {"type": "game_server", "name": a.name or (info or {}).get("hostname") or last_name or "Game server"}
    if a.address:
        s["address"] = a.address
    if a.url:
        s["url"] = a.url
    if a.cta:
        s["cta"] = a.cta
    if a.image_url:
        s["image_url"] = a.image_url
    if info is None:
        s.update(online=False, players_online=0, players=[])
        return s
    s.update(
        online=True,
        players_online=info["players"],
        players_max=info["max_players"],
        players=[] if a.no_player_names else names[:50],
        map=info["map"],
        game=a.game or info["game"],
        description=info["gametype"][:200],
    )
    return s


def main() -> int:
    a = parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest = Ingest(a.ingest_url, a.ingest_secret)

    online: bool | None = None
    known: set[str] = set()
    last_name = ""
    last_sent = 0.0
    heartbeat_s = a.heartbeat * 60

    while True:
        info, names = query(a.host, a.port, not a.no_player_names)
        now_online = info is not None
        if info:
            last_name = info["hostname"] or last_name
        state = build_state(a, info, names, last_name)
        current = set(names)

        events: list[tuple[str, dict | None]] = []
        if online is None or now_online != online:
            events.append(("server.online" if now_online else "server.offline", None))
        if now_online and online is not None and not a.no_player_names:
            for n in sorted(current - known):
                events.append(("player.joined", {"player": n}))
            for n in sorted(known - current):
                events.append(("player.left", {"player": n}))

        if events:
            for ev, data in events:
                log.info("%s %s", ev, (data or {}).get("player", ""))
                ingest.send(ev, data, state)
            last_sent = time.time()
        elif heartbeat_s and time.time() - last_sent >= heartbeat_s:
            log.info("heartbeat: %s players online", state.get("players_online", 0))
            ingest.send(None, None, state)
            last_sent = time.time()

        online = now_online
        known = current if now_online else set()
        if a.once:
            return 0
        time.sleep(max(5, a.interval))


if __name__ == "__main__":
    sys.exit(main())
