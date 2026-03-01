# GarSync

GarSync is a microservice and CLI tool designed to bridge the gap between Garmin Connect's proprietary cloud and a personal developer platform. It extracts activities, daily biometrics (HRV, Resting HR, Body Battery, Stress), and sleep data, outputting it as normalized, structured JSON.

## Features

- **Automated Extraction:** Pulls activities and biometric data from Garmin Connect.
- **Resilient:** Built-in retry logic to handle network timeouts and API rate limiting.
- **Containerized:** Ready for deployment via Docker Compose.
- **Structured Data:** Outputs normalized JSON suitable for time-series databases or personal data lakes.

## Getting Started

### Local Setup (Development)

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Run the CLI:
   ```bash
   poetry run garsync --help
   ```

### Docker Compose & Makefile

The project includes a `docker-compose.yml` and a `Makefile` to simplify operations without needing a complex orchestrator. The extracted data is stored in a local `./data` volume.

**1. Setup Environment & Credentials**

Create a local `data` directory and initialize your encrypted secrets file:

```bash
make setup
```

This will automatically create a `secrets.env.enc` file if it doesn't exist. Now, edit the secrets (it will temporarily decrypt them in your default editor):

```bash
make secrets-edit
```

Fill in your Garmin Connect credentials:

```ini
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password
```

Save and close your editor. SOPS will automatically re-encrypt the file. You do **not** need an unencrypted `.env` file sitting around anymore!

**2. Build the Image**

```bash
make build
```

**3. Run the Sync Job**

Executes the synchronization process and outputs the structured JSON to `data/sync_result.json`:

```bash
make run
```

**4. View the Dashboard**

You can spin up an interactive data visualization dashboard based on Streamlit that reads your latest sync file:

```bash
make ui
```

Then visit `http://localhost:8501` in your browser.

**5. Additional Commands**

- Drop into a shell inside the container for debugging: `make shell`
- Clean up containers and local data output: `make clean`

## Development

- **Linting:** Run `poetry run ruff check .`
- **Type Checking:** Run `poetry run mypy src`
- **Testing:** Run `poetry run pytest`
