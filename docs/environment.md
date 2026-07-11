# Phase-1 Development Environment

Inventory recorded on 2026-07-10 for the local Windows development host.

| Tool | Verified version | Notes |
|---|---:|---|
| uv | 0.10.3 | User-local installation |
| Python | 3.12.12 | Resolved with `uv run --python 3.12` |
| Java | Temurin 17.0.19+10 | Side-by-side JDK; Java 21 remains installed |
| Node.js | 24.13.0 | Meets the Node 20+ requirement |
| pnpm | 9.15.9 | Pinned in the user npm prefix |
| Git | 2.52.0.windows.1 | Feature branch workflow |
| Docker Compose | 5.0.0-desktop.1 | Local PostgreSQL/CI dependency path |
| Joern | 4.0.579 | Docker image pinned by digest in `config/joern.lock.json` |
| psql | not installed | Not required; project probes/loaders use psycopg |
| .NET SDK | not installed | Phase-3 C# generation is verified deterministically; compile evidence remains `COMPILE_NOT_RUN` until a pinned SDK is installed |

Local JDK 17 path:

```text
C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot
```

PowerShell sessions that have not refreshed the machine environment can select it with:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

Shared EC2 and RDS resources were not accessed or modified during this inventory.
