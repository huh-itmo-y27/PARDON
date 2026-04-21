# Publish Docs

## GitHub Pages (recommended)

This repository includes a GitHub Actions workflow:

- `.github/workflows/docs-deploy.yml`

It builds MkDocs and deploys to GitHub Pages on push to `main`.

## One-time setup

1. Open repository settings on GitHub.
2. Go to `Settings` -> `Pages`.
3. Under `Build and deployment`, set `Source` to `GitHub Actions`.
4. Push your changes to `main`.

Your docs should appear at:

- `https://huh-itmo-y27.github.io/PARDON/`

## Local preview

```bash
uv run mkdocs serve -f docs/mkdocs.yml
```

## Manual build

```bash
uv run mkdocs build -f docs/mkdocs.yml
```
