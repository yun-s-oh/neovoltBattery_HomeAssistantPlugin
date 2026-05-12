# Instructions

- Rules, skills, and workflows live in the `.agents/` directory at the project root.
- For project architecture and domain context, see [context.md](context.md).
- For the automatic recovery system design, see [recovery_system.md](recovery_system.md).

## Development

### Docker (Preferred)
Use Docker Compose to run a local Home Assistant instance with the integration mounted:
```bash
docker-compose up -d
```

### Virtual Environment (Deprecated)
The Core installation method is deprecated. Only use for quick tests:
```bash
./venv/bin/hass -c config
```

## Logs

- [Changelog](logs/changelog.md) — Always log notable changes here.