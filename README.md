# Mongolia-map-database-

Mongolia desertification atlas for exploring monthly and yearly data by aimag,
year, month, and region.

The atlas includes a separate sources section linking to national news, UNDP
information, and a Mongolian research journal article. Its 2026 national
desertification estimate is identified separately from the atlas's 2002–2022
aimag dataset.

## Project structure

- `app.py` — root entry point for the web application
- `code/` — FastAPI application and analysis scripts
- `database/` — CSV, Excel, and GeoPackage datasets

The GeoPackage is stored with Git LFS. Install Git LFS before cloning or
downloading this repository so the actual dataset is available.

## Deploy to Fly.io

The app is configured to run in a Docker container on port `8080`. The
GeoPackage and CSV are included in the image as read-only application data.
The GeoPackage is about 354 MB, so the first image build and deploy may take
longer and use substantial image storage.

Requirements:

- `flyctl` and a Fly.io account
- Git LFS, with the GeoPackage downloaded locally

From the project root:

```sh
git lfs pull
fly auth login
fly launch --copy-config --no-deploy
fly deploy
```

`fly.toml` uses `mongolia-desert-atlas-enhuush` as a suggested app name. Fly.io
app names must be globally unique; if it is already taken, change the `app`
value in `fly.toml` before running `fly launch`.

Fly.io builds the Docker image remotely, so a local Docker daemon is optional.
The `/healthz` endpoint checks that the CSV data loaded and both required
datasets are present. Fly.io uses it to verify that the app is ready.
