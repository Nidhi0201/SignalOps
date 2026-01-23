# Installing Docker Desktop for SignalOps

## Quick Install (macOS)

### Step 1: Download Docker Desktop

**Option A: Direct Download**
1. Visit: https://www.docker.com/products/docker-desktop/
2. Click "Download for Mac"
3. Choose the correct version:
   - **Apple Silicon** (M1/M2/M3): Download "Mac with Apple chip"
   - **Intel Mac**: Download "Mac with Intel chip"

**Option B: Using Homebrew** (if you have Homebrew)
```bash
brew install --cask docker
```

### Step 2: Install Docker Desktop

1. Open the downloaded `.dmg` file
2. Drag the Docker icon to your Applications folder
3. Open Docker from Applications (or Spotlight: Cmd+Space, type "Docker")
4. Follow the setup wizard
5. You may need to enter your password to allow Docker to run

### Step 3: Start Docker Desktop

1. Open Docker Desktop from Applications
2. Wait for Docker to start (you'll see a whale icon in your menu bar)
3. The first time may take a few minutes to initialize

### Step 4: Verify Installation

Open a terminal and run:
```bash
docker --version
docker compose version
```

You should see version numbers. If you get "command not found", make sure Docker Desktop is running.

### Step 5: Start SignalOps

Once Docker is running:
```bash
cd /Users/nidhiprajapati/Desktop/SignalOps
docker compose up -d
```

Wait 10-15 seconds, then verify:
```bash
curl -u admin:admin http://localhost:9200
```

## Troubleshooting

**"Docker daemon is not running"**
- Make sure Docker Desktop is open and running
- Check the menu bar for the Docker whale icon
- If the icon isn't there, open Docker Desktop from Applications

**"Permission denied"**
- Docker Desktop handles permissions automatically
- If issues persist, check Docker Desktop → Settings → Resources → File Sharing

**Docker Desktop won't start**
- Make sure you have enough disk space (Docker needs ~4GB)
- Check System Preferences → Security & Privacy → Allow Docker
- Restart your Mac if needed

**Still having issues?**
- Check Docker Desktop logs: Docker Desktop → Troubleshoot → View logs
- Make sure virtualization is enabled (usually automatic on Mac)

## System Requirements

- macOS 10.15 or newer
- At least 4GB RAM (8GB+ recommended)
- VirtualBox prior to version 4.3.30 must NOT be installed

## After Docker is Running

Once Docker Desktop is running, you can start SignalOps:

```bash
cd /Users/nidhiprajapati/Desktop/SignalOps

# Start all services
docker compose up -d

# Wait 10-15 seconds, then test
curl -u admin:admin http://localhost:9200

# Ingest sample logs
./test-sample-logs.sh

# Open dashboard
open http://localhost:3000
```

## Alternative: Cloud Services (Advanced)

If you can't install Docker, you could use:
- **OpenSearch Cloud**: AWS OpenSearch Service, Elastic Cloud
- **Redis Cloud**: Redis Cloud, Upstash
- **Postgres Cloud**: Supabase, Neon, Railway

However, Docker is the easiest and recommended approach for local development.
