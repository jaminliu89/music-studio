# DME CI Trigger

This file exists only to trigger the first pull-request validation after introducing `.github/workflows/dme-ci.yml`.

Acceptance target:
- `npm ci`
- `npm run dme:smoke`
- `npm run build`

The file may be removed after CI is proven healthy.
