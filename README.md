# ESNFlux

ESNFlux is the self-contained operations and Discord system for **ESN SMP**. It monitors the Minecraft Bedrock server, tracks observable player activity, records statistics and incidents, exposes SMP/status data to the ESN website, and posts branded SMP events to a configured Discord logging channel.

## Scope

ESNFlux is intentionally limited to:
- ESN SMP monitoring and statistics
- SMP-related Discord functionality
- ESN website SMP/status API

It does **not** power unrelated ESN projects and contains no AI features.

## Server

- Host: `esnsmp.ggwp.cc`
- Port: `17058`
- Platform: Minecraft Bedrock

## Main capabilities

- Online/offline monitoring
- Player count and player-list tracking when supported by the Bedrock query protocol
- Player sessions and activity history
- Uptime, downtime, latency and health tracking
- Incidents and recovery detection
- SMP statistics and leaderboards
- Black/green branded Discord logging embeds
- Staff-controlled Discord logging channel
- Public website status/statistics API
- Diagnostics and database backups
- Automated tests

## Development

Python 3.11+ is recommended. Copy `.env.example` to `.env`, install dependencies from `requirements.txt`, and run `python -m esnflux`.

Never commit real Discord tokens, API secrets, or production credentials.
