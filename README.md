# LinkHarbor for FiveM / RedM

A single-file Python agent that polls a FiveM (GTA V) or RedM (Red Dead
Redemption 2) server and pushes the live state to your
[LinkHarbor](https://linkharbor.com) bio page — a game-server card with
Online/Offline, "32 / 64" players, player names and your `cfx.re/join` link,
plus join/leave events for push notifications to your followers.

It uses the public HTTP endpoints every FiveM/RedM server already exposes on
its game port (`/dynamic.json`, `/players.json`, `/info.json`), so nothing is
installed on the server. Standard library only, Python 3.10+.

Part of the [LinkHarbor integrations](https://github.com/linkharbor/linkharbor-integrations)
family (one repo per game).

## Setup

```bash
git clone https://github.com/linkharbor/linkharbor-fivem
cd linkharbor-fivem

export LH_INGEST_URL="https://api.linkharbor.com/v1/ingest/123"   # dashboard → Integrations → Custom (API)
export LH_INGEST_SECRET="…"

python3 agent.py --host 203.0.113.10 --port 30120 \
  --name "My RP Server" --address "cfx.re/join/abcdef" \
  --url "https://discord.gg/xyz" --interval 60
```

Try `--once -v` first. Run it as a service with `linkharbor-fivem.service`
(systemd; secrets go into `/etc/linkharbor-fivem.env`, `chmod 600`). If the
server runs on the same machine, `--host 127.0.0.1` works even when the
endpoints are firewalled from the outside.

## Events sent

| Event | When | Template variables |
|---|---|---|
| `server.online` | first successful poll, or back after being unreachable | `{name}`, `{players_online}`, `{players_max}`, `{map}` |
| `server.offline` | the server stopped answering | `{name}` |
| `player.joined` | a new name appears in `players.json` | `{player}` + the above |
| `player.left` | a name disappears | `{player}` + the above |

The state is sent with every event and every `--heartbeat` minutes (default
10). `--no-player-names` sends counts only.

Suggested push rule (dashboard → Integrations → Push rules → Custom (API) →
`player.joined`): batch window 10 min, title "🎮 {count} players joined", body
"{player_list} are now on {name}", minimum pause 5 min.

## Options

```
--host HOST            server IP / hostname (required)
--port PORT            FiveM/RedM HTTP port (default 30120)
--name NAME            card title (default: the server's hostname, colour codes stripped)
--address ADDRESS      address shown on the card (cfx.re/join/… or ip:port)
--url URL              link behind the card's button
--cta TEXT             button label (default "Join server")
--game TEXT            game label (default FiveM / RedM, detected)
--image-url URL        banner image (large layout)
--interval SECONDS     polling interval (default 60, min 5)
--heartbeat MINUTES    state-only update interval (default 10, 0 = only on change)
--no-player-names      don't send player names
--once                 poll once, send, exit
-v                     verbose logging
```

## License

[MIT](LICENSE) — © 2026 EMI Solutions OÜ.
