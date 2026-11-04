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

- A Fly.io account and `flyctl`
- The GeoPackage downloaded through Git LFS
- A Fly.io deploy token saved as the GitHub Actions repository secret
  `FLY_API_TOKEN`

Create the Fly app once from the project root. Replace `<your-org>` with the
organization slug shown by `fly orgs list`:

```sh
fly auth login
fly apps create mongolia-desert-atlas-enhuush --org <your-org>
fly tokens create deploy -x 999999h
```

Copy the full deploy token into GitHub repository **Settings → Secrets and
variables → Actions** as `FLY_API_TOKEN`. Do not commit the token or paste it
into chat. After this setup, pushes to `main` deploy the app automatically.
If Fly.io says the app name is already taken, choose another unique name and
update the `app` value in `fly.toml` before creating the app.

Fly.io builds the Docker image remotely, so a local Docker daemon is optional.
The `/healthz` endpoint checks that the CSV data loaded and both required
datasets are present. Fly.io uses it to verify that the app is ready.
