# ESNFlux

ESNFlux is the operations and Discord system for **ESN SMP**. It monitors the Minecraft Bedrock server, tracks observable player activity, records server samples and incidents, exposes SMP/status data to the ESN tracking website, and posts SMP events to a configured Discord logging channel.

## Scope

ESNFlux is intentionally limited to:
- ESN SMP monitoring and statistics
- SMP-related Discord functionality
- ESN tracking website SMP/status API and dashboard

It does **not** power unrelated ESN projects and contains no AI features.

## Official tracking website

- `https://esnoffical.com`

The Flux service can serve the dashboard directly from `/`, while the API remains available under `/api/*`. The dashboard automatically refreshes live SMP data every 30 seconds.

## Server

- Host: `esnsmp.ggwp.cc`
- Port: `17058`
- Platform: Minecraft Bedrock

## Current capabilities

- Online/offline monitoring
- Player count and observable player-name samples when supported by the Bedrock query protocol
- Player session tracking with restart recovery
- Persistent peak-player tracking
- Server samples with latency
- Aggregated uptime, average players, peak, and latency statistics
- Outage incident creation and recovery resolution
- Branded Discord status, player, and peak logs
- `/smp status` and `/smp players` slash commands
- Website health, live status, players, statistics, and history APIs
- CORS restricted to `https://esnoffical.com`
- Public SMP telemetry history for the dashboard
- Automated unit/integration tests
- Docker and Docker Compose deployment support
- CI test and production-image build validation

## API

- `GET /api/health`
- `GET /api/smp/status`
- `GET /api/smp/players`
- `GET /api/smp/stats?limit=500`
- `GET /api/smp/history?limit=100`

The API exposes SMP telemetry only; it does not expose Discord credentials, environment secrets, or private account data.

## Important limitation

The Bedrock query protocol may return a player count without a complete player-name sample. ESNFlux deliberately treats that situation as **unknown player identity data** instead of incorrectly announcing players as leaving.

## Development

Python 3.11+ is recommended. Copy `.env.example` to `.env`, install dependencies from `requirements.txt`, and run `python -m esnflux`.

Never commit real Discord tokens, API secrets, database files, or production credentials.

## Production deployment

For a persistent deployment:

```bash
docker compose up -d --build
```

The Compose configuration:
- restarts Flux automatically after a container failure
- persists `/app/data` in a Docker volume
- exposes port `8080`
- performs an HTTP health check against `/api/health`
- builds the dashboard into the production image

Put HTTPS/reverse-proxy termination in front of the service and point `esnoffical.com` at that public service. Do not expose the container's raw HTTP port directly to the public internet unless the hosting environment provides equivalent network protection.

## Production checklist

Before going live:
1. Configure `DISCORD_TOKEN`.
2. Configure the ESN Discord guild ID and SMP log channel ID.
3. Keep `/app/data` on persistent storage so incidents, sessions, samples, and the SMP peak survive restarts.
4. Point `esnoffical.com` to the deployed Flux service through HTTPS.
5. Confirm the host can reach `esnsmp.ggwp.cc:17058`.
6. Verify `/api/health`, `/api/smp/status`, `/api/smp/stats`, Discord slash commands, and the logging channel.
7. Verify the dashboard from a normal browser and from a mobile browser.
8. Confirm the Docker health check reports healthy.
9. Keep the first production run supervised so Discord permissions, SMP query behavior, API connectivity, and database persistence can be verified.
