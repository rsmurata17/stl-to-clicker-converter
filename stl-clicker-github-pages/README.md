# STL to Cherry MX Clicker Converter

Static GitHub Pages version of the STL clicker converter.

## Files

- `index.html`
- `style.css`
- `app.js`

## Run locally

Because this uses ES modules, open it through a local server:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## Deploy to GitHub Pages

1. Create a new GitHub repository.
2. Upload `index.html`, `style.css`, and `app.js`.
3. Go to **Settings → Pages**.
4. Under **Build and deployment**, choose:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/root**
5. Save.
6. Wait for GitHub to publish the site.

## Important notes

This runs entirely in the browser. STL booleans are much harder in browser JavaScript than in Python `trimesh`, so very dense, messy, or non-watertight STLs may fail.

For the most reliable production version, use a server backend with Python `trimesh` or Manifold.
