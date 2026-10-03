# Maya Core

Maya Core is the FastAPI service that provides Maya's identity, configuration,
request context, model routing, and chat foundation.

## Local execution

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the development server from the repository root:

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

## Container execution

Build the image:

```bash
docker build -t maya-core .
```

Run the production server while mounting configuration from the host:

```bash
docker run --rm \
  -p 8000:8000 \
  -v "$PWD/configs:/app/configs:ro" \
  maya-core
```

The image starts with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Configuration is read from `configs/maya-config.yaml` and can be changed by
updating the mounted host file.

## Endpoints

- `GET /health` — service health information
- `GET /identity` — Maya identity configuration
- `GET /config/status` — safe configuration status
- `POST /chat` — chat request entry point
