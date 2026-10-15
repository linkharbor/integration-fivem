# LinkHarbor for FiveM and RedM

A single-file Python agent that polls a FiveM (GTA V) or RedM (Red Dead Redemption 2) server and shows it on your [LinkHarbor](https://linkharbor.com) bio page: online or offline, "32 / 64" players, player names and your `cfx.re/join` link. Joins and leaves become events your followers can get push notifications for.

It reads the HTTP endpoints every FiveM and RedM server already serves on its game port (`/dynamic.json`, `/players.json`, `/info.json`), so nothing is installed on the server. Python 3.10 or newer, standard library only.

Part of the [LinkHarbor integrations](https://github.com/linkharbor/integrations) family, one repo per game.

## Setup

```bash
git clone https://github.com/linkharbor/integration-fivem
cd integration-fivem

export LH_INGEST_URL="https://dock.at-harbor.com/v1/ingest/123"   # dashboard: Integrations, Custom (API)
export LH_INGEST_SECRET="…"

python3 agent.py --host 203.0.113.10 --port 30120 \
  --name "My RP Server" --address "cfx.re/join/abcdef" \
  --url "https://discord.gg/xyz" --interval 60
```

Start with `--once -v`. Then run it as a service, see `integration-fivem.service` for systemd; the secrets go into `/etc/integration-fivem.env` with `chmod 600`. If the agent runs on the game server itself, `--host 127.0.0.1` works even when the endpoints are firewalled from outside.

## Events sent

| Event | When | Template variables |
|---|---|---|
| `server.online` | the first successful poll, or the server is back after being unreachable | `{name}`, `{players_online}`, `{players_max}`, `{map}` |
| `server.offline` | the server stopped answering | `{name}` |
| `player.joined` | a new name appears in `players.json` | `{player}` and the above |
| `player.left` | a name disappears | `{player}` and the above |

The state is sent with every event and every `--heartbeat` minutes (default 10). `--no-player-names` sends counts only.

Suggested push rule (dashboard, Integrations, Push rules, Custom (API), event `player.joined`): batch window 10 minutes, title "🎮 {count} players joined", body "{player_list} are now on {name}", minimum pause 5 minutes.

## Options

```
--host HOST            server IP or hostname (required)
--port PORT            FiveM/RedM HTTP port (default 30120)
--name NAME            card title (default: the server's hostname without colour codes)
--address ADDRESS      address shown on the card (cfx.re/join/… or ip:port)
--url URL              link behind the card's button
--cta TEXT             button label (default "Join server")
--game TEXT            game label (default FiveM or RedM, detected)
--image-url URL        banner image for the large layout
--interval SECONDS     polling interval (default 60, minimum 5)
--heartbeat MINUTES    state-only update interval (default 10, 0 = only on change)
--no-player-names      send counts only
--once                 poll once, send, exit
-v                     verbose logging
```

## License

[MIT](LICENSE). © 2026 EMI Solutions OÜ.
