# ESNFlux

ESNFlux is the operations and Discord system for **ESN SMP**. It monitors the Minecraft Bedrock server, tracks observable player activity, records server samples and incidents, exposes SMP/status data to the ESN website, and posts SMP events to a configured Discord logging channel.

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

## Current capabilities

- Online/offline monitoring
- Player count and observable player-name samples when supported by the Bedrock query protocol
- Player session tracking
- Persistent peak-player tracking
- Server samples with latency
- Outage incident creation and recovery resolution
- Branded Discord status, player, and peak logs
- `/smp status` and `/smp players` slash commands
- Website status, players, health, and history API
- Optional API-key protection for history
- Automated unit/integration tests
- Docker-based deployment support

## Important limitation

The Bedrock query protocol may return a player count without a complete player-name sample. ESNFlux deliberately treats that situation as **unknown player identity data** instead of incorrectly announcing players as leaving.

## Development

Python 3.11+ is recommended. Copy `.env.example` to `.env`, install dependencies from `requirements.txt`, and run `python -m esnflux`.

Never commit real Discord tokens, API secrets, database files, or production credentials.

## Production checklist

Before deployment:
1. Configure `DISCORD_TOKEN`.
2. Configure the ESN Discord guild ID and SMP log channel ID.
3. Configure a strong `API_KEY` if the history endpoint is exposed outside a trusted private network.
4. Keep `/app/data` on persistent storage so incidents, sessions, samples, and the SMP peak survive restarts.
5. Expose the API through HTTPS/reverse proxy if it is publicly reachable.
6. Confirm the host can reach `esnsmp.ggwp.cc:17058`.
7. Start Flux and verify `/api/health`, `/api/smp/status`, Discord slash commands, and the configured logging channel.
8. Keep the first production run supervised so startup, Discord permissions, and SMP query behavior can be verified.
