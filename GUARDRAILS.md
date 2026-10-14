# Guardrails — Road Condition Assessor

This document outlines the safety, quality, and operational boundaries for the Road Condition Assessor application.

## Data Quality and Accuracy

### AI Analysis Limitations
- **Visual estimates only**: crack width, rut depth, and pavement type are visual estimates from photos, not direct measurements.
- **Target accuracy**: AI analysis should match human surveyor assessment on ≥80% of segments. Real-world accuracy depends on photo quality and lighting.
- **Photo quality critical**: poor lighting, blur, glare, or standing water significantly reduce accuracy. Always use clear, well-lit photos taken perpendicular to the road surface.
- **Weather effects**: wet surfaces and shadows distort distress detection. Avoid surveying during or immediately after rain.

### Manual Validation Required
- **Always review AI results**: do not rely solely on AI-generated values. The surveyor must verify all numbers before saving.
- **Correct obvious errors**: if the AI significantly misestimates area, width, or count, manually update the worksheet.
- **Field knowledge trumps AI**: the surveyor's judgment about pavement type (asphalt vs. concrete vs. paving) overrides AI classification when uncertain.

### Data Consistency
- **SDI formula frozen**: the Bina Marga SDI calculation (Panduan Survai Kondisi Jalan SMD-03/RCS) is fixed and will not change without explicit decision and documentation.
- **Condition classes stable**: Good, Fair, Lightly damaged, Heavily damaged boundaries (SDI < 50, 50–100, 100–150, ≥150) are standards and will not shift.
- **Exported data must be valid**: before sharing CSV/GeoJSON exports, verify that:
  - All `section` and `sta` fields are non-empty.
  - SDI values fall within the ranges that define each condition class.
  - Coordinates are valid (lat -90 to 90, lon -180 to 180) or empty.
  - Dates are in ISO 8601 format (YYYY-MM-DD).

## AI Provider Constraints

### DeepSeek (Default)
- **Rate limits**: monitor for HTTP 429 errors; back off and retry after a short delay.
- **Cost**: billed per token; keep an eye on usage to avoid surprise costs.
- **Availability**: DeepSeek API outages are rare but possible. Have a fallback plan.
- **Model changes**: DeepSeek may update `deepseek-flash` without notice. Test after platform updates.

### Claude (Alternative)
- **Accuracy**: generally higher than DeepSeek on road defects, but slower and more expensive.
- **Authentication**: API key must be kept secret; never commit `.streamlit/secrets.toml`.
- **Quota**: check your account's rate limit and token cap. Some accounts have stricter quotas than others.

### Offline Model (RF-DETR)
- **Status**: in preparation. Will be optional when ready.
- **Purpose**: eliminate API costs and latency for organizations with large survey volumes.
- **Accuracy**: expected to be comparable to DeepSeek but requires GPU hardware for fast inference.

## Vibration Sensor (RMS) Constraints

### Relative Roughness Only
- **Not IRI**: RMS vertical acceleration is NOT the official International Roughness Index (IRI). It is a relative indicator only.
- **Same conditions required**: compare RMS values only between recordings with:
  - Same vehicle model and weight.
  - Same speed (within ±5 km/h).
  - Same phone position and mounting (same axis, same location on vehicle).
- **Errors**: incorrect vehicle speed, phone tilt, or acceleration sensor bias will skew results.

### Data Validation
- **Minimum samples**: at least 10 samples per segment; fewer samples give unreliable estimates.
- **GPS accuracy**: if using GPS-derived distances, verify that lat/lon are not jumping or drifting.
- **Outliers**: segments with RMS > 2× the median may indicate sensor errors, potholes, or bumps; review manually.

## CSV Import and Export

### Column Requirements
Required columns for import:
- `section` (text): road section name (e.g., "Main Street").
- `sta` (text): station in km+m format (e.g., "2+100").
- `sdi` (number): Surface Distress Index, 0–400+.

Optional columns:
- `length_m` (number): segment length in meters.
- `crack_pct` (number): crack area as percentage.
- `potholes_per_100m` (number): pothole density.
- `lat` (number): latitude.
- `lon` (number): longitude.
- `date` (text): ISO 8601 date.

### Compatibility
- **CSV delimiter**: auto-detected (comma, semicolon, or tab).
- **GeoJSON format**: FeatureCollection with Point geometries and properties matching the column names above.
- **Backward compatibility**: older files with Indonesian column names (`ruas`, `tgl`, `cls`) are automatically converted on import.
- **No data migration**: once imported, old column names are converted; the app always exports English column names.

## Security and Privacy

### API Keys
- **Never hardcode**: API keys must be in `.streamlit/secrets.toml` or environment variables, never in source code.
- **Rotation**: if an API key is ever exposed, delete it from the provider and generate a new one immediately.
- **Least privilege**: use API keys scoped to minimal permissions (vision + structured output only for Claude, image analysis only for DeepSeek).

### Data Storage
- **Local by default**: segment data is stored in `data/segmen.json` on the user's machine, not on a server.
- **No cloud upload**: without explicit setup, the app does not upload survey data anywhere.
- **Sharing responsibility**: if you export CSV and share it, you are responsible for redacting sensitive location or administrative data.

### Photo Uploads
- **Temporary only**: photos uploaded to the app are never saved to disk; they are held in memory only for analysis.
- **AI visibility**: when using Claude or DeepSeek, photos are sent to those providers' servers (subject to their privacy policies). Review your privacy policy requirements before analyzing sensitive road or location data.

## Testing and Validation

### Before Deployment
- Run the full test suite: `python -m pytest -v`.
- Test each data source manually (photo, video, multiple photos, CSV import, sensor).
- Validate a sample of AI-analyzed photos against manual surveyor assessment.
- Spot-check CSV exports to ensure all required columns are present and valid.

### Model Updates
- If the AI model is updated (Claude, DeepSeek, or RF-DETR), re-validate accuracy on a representative sample of roads and lighting conditions.
- Document any changes in accuracy or behavior.
- If accuracy drops below 75%, pause deployments and investigate.

### Dependencies
- Pin all Python dependencies in `requirements.txt` to exact versions.
- Review security advisories monthly (use `pip-audit` or similar).
- Do not auto-upgrade libraries in production; test updates in a staging environment first.

## Operational Limits

### Scalability
- **Single user**: the app is designed for one surveyor at a time (browser-based session state).
- **Data volume**: segment lists with >1,000 entries may slow the UI; consider archiving old surveys to separate files.
- **Concurrent AI calls**: each AI provider has rate limits. Do not launch more than 1–2 concurrent analyses.

### Offline Operation
- **No internet, no AI**: without a network connection, AI analysis is unavailable. Manual worksheet entry will work.
- **GPS**: phone accelerometer data (sensor mode) does not require internet, but GPS coordinates may be unreliable without connectivity.
- **Syncing**: if working offline, export CSV before losing internet, then merge results manually after regaining connectivity.

### Performance Targets
- **Photo analysis**: 10–60 seconds per photo (depends on photo size, AI provider, and server load).
- **Video analysis**: 5–10 minutes for a 2-minute video with 5 key frames (5 AI calls × ~1 min each).
- **Startup**: app should load in <5 seconds on a standard laptop.

## Maintenance and Support

### Bug Reports
- Report bugs with:
  - Steps to reproduce.
  - Screenshot or error message.
  - Python version, OS, and Streamlit version.
  - Reproducible sample data (photo, CSV, or sensor file if applicable).
- Do not include real survey data (redact locations and sensitive information).

### Feature Requests
- Document the use case: who needs this, and why?
- Link to relevant Bina Marga standards or academic papers if applicable.
- Propose acceptance criteria: how will you know the feature works?

### Known Limitations (as of October 2026)
- RF-DETR offline model integration not yet complete.
- Multi-user collaboration not supported (single local file only).
- No mobile app (browser only on desktop/tablet).
- Distress mapping (drawing boxes) only works in photo analysis mode, not video.
- Custom condition classes or SDI formulas not supported.

## Contribution Guidelines

### Code Changes
- All changes must pass the test suite.
- Add tests for new features.
- Keep comments and docstrings in English.
- Do not rename data structure fields (`section`, `sta`, `sdi`, etc.) without a migration plan.

### Translations
- UI text, comments, and error messages must be in English.
- If translating the UI to other languages, keep the underlying code (identifiers, column names) in English for consistency.

### Model Updates
- If updating the AI model or SDI formula, document:
  - What changed and why.
  - Impact on historical data.
  - Validation results on a sample dataset.
  - Migration steps for existing surveys.

## Emergency Procedures

### API Outage
If Claude or DeepSeek is unavailable:
1. The app will show an error when you try to analyze a photo.
2. Switch to manual worksheet entry (leave "Analyze with AI" unchecked).
3. Check the provider's status page for updates.
4. If the outage lasts >1 hour, consider switching to the other provider (edit `.streamlit/secrets.toml` and restart the app).

### Data Corruption
If `data/segmen.json` is corrupted:
1. The app will fail to load the segment list.
2. Restore from the most recent backup (if you have one).
3. If no backup exists, manually re-enter recent surveys from your field notes or photos.
4. Use CSV import to bulk-add recovered segments.

### Accidental Data Loss
If you accidentally delete segments:
1. Ctrl+Z does not work (file-based storage).
2. Restore from a backup if available.
3. If not, re-survey the affected road segments.

---

## Summary

The Road Condition Assessor is a **tool to assist surveying, not replace it**. Always:
- **Verify AI results** with your field knowledge.
- **Validate exported data** before sharing.
- **Keep API keys secure**.
- **Test extensively** before deploying to new environments.
- **Document deviations** from the standard SDI method.

For questions or incidents, contact the project maintainer and include all relevant details (error message, data sample, environment info).
