# PRD — Road Condition Assessor

Status: draft 1 · Written from the existing code · Figures marked **(assumption)** need confirmation.

## 1. Summary and problem

Manual pavement condition surveys are slow, depend on the surveyor's subjective judgment, and produce results that are hard to compare across road sections or over time. This application calculates the Bina Marga **Surface Distress Index (SDI)** automatically from distress inputs, and can help fill those inputs through AI analysis of photos and video. The output is a condition class, a recommended treatment, a map, and data export.

## 2. Goals and success metrics

| Goal | Metric | Target |
|---|---|---|
| Faster assessment | Time to assess one 100 m segment | ≤ 2 minutes with AI assistance **(assumption)** |
| Trustworthy AI results | AI condition class matches the surveyor's | ≥ 80% of segments **(assumption)** |
| Affordable | API cost per photo | Stays small; tracked per provider |
| Reusable results | Exported CSV/GeoJSON can be re-imported | 100% |

## 3. Users

- **Field surveyors**: capture photos, video, or sensor recordings; fill in and correct the SDI worksheet.
- **Road agency staff / road managers**: review the segment list, condition classes, and treatment priorities.
- **Researchers / students**: compare road sections, evaluate AI accuracy, use sensor data.

## 4. Scope

**In scope**
- Bina Marga SDI calculation (SMD-03/RCS) and 4 condition classes.
- Five data sources: single photo, short video, multiple photos, CSV/GeoJSON import, vibration sensor.
- Optional automatic photo analysis with DeepSeek or Claude.
- Segment list storage, CSV and GeoJSON export, cross-section statistics.

**Out of scope (for now)**
- Official IRI and PCI.
- Login, multi-user support, a central database.
- Native mobile app.

## 5. Functional requirements

| ID | Requirement | File |
|---|---|---|
| F1 | Calculate SDI from crack area, crack width, number of potholes, rutting, and segment length. Classes: Good (< 50), Fair (50–100), Lightly damaged (100–150), Heavily damaged (≥ 150), each with a suggested treatment. | `sdi.py` |
| F2 | Single photo: SDI worksheet filled manually or with AI; distress marked on the photo. | `app.py`, `analisis.py` |
| F3 | Short video: extract the sharpest frames evenly, analyze each frame, and merge (crack area averaged, crack width and rutting by median, potholes = highest count in a single frame). | `video.py` |
| F4 | Multiple photos: consecutive stations (STA) from a start STA plus a distance between photos; results can be corrected in a table before saving. | `ui_lain.py` |
| F5 | Import CSV/GeoJSON with required columns `section`, `sta`, `sdi`; condition is recalculated from SDI. | `impor.py` |
| F6 | Vibration sensor: read phone accelerometer CSV, compute vertical vibration RMS per segment, show a chart, a map (when GPS is available), and a CSV download. | `sensor.py` |
| F7 | Choose the AI provider via `AI_PROVIDER` (DeepSeek by default, Claude optional). | `ai.py`, `analisis_deepseek.py` |
| F8 | Read location and time from GPS/EXIF in JPEG photos when present. | `exif_gps.py` |
| F9 | Save the segment list to `data/segmen.json`; export CSV and GeoJSON. | `storage.py` |
| F10 | Statistics: mean, standard deviation, and 95% interval per road section; SDI smoothed with a Gaussian kernel along the STA; flag outlier segments (\|z\| > 2). | `statistik.py` |

## 6. Non-functional requirements

- **No mandatory dependency on AI**: without an API key the application can still be used manually.
- **Human-correctable**: every AI-produced number can be edited before saving.
- **Clear limits**: crack width and rut depth from photos are only visual estimates; vibration RMS is only a relative roughness indicator (not IRI) and should only be compared across recordings with the same vehicle, speed, and phone position.
- **Local storage**: data is stored in local files; API keys live in `.streamlit/secrets.toml` and must not be committed.
- **Testing**: core logic is covered by `pytest` (`tests/`).

## 7. Roadmap

1. **Offline detection model (RF-DETR Nano)**: the Colab notebook `notebooks/latih_rfdetr.ipynb` already exists (classes D00, D10, D20, D40 from the RDD dataset). Next: train, export to ONNX, and integrate as an offline provider in `ai.py`.
2. **Field validation**: compare AI/model results against surveyor assessments on real data.
3. **Optional**: a shared database and login if many surveyors use it.

## 8. Risks and assumptions

| Risk / assumption | Impact | Mitigation |
|---|---|---|
| Poor photo quality (dark, blurry, standing water) | Distress is misestimated | Pick sharp frames, allow manual correction |
| Crack width and rut estimates from photos are inaccurate | Biased SDI | Mark as estimates, allow manual input |
| Dependence on third-party APIs (cost, quota, model changes) | Service disruption | Two providers, manual mode, offline model |
| RDD training data is limited to certain conditions | Lower accuracy on Indonesian roads | Field validation, add local data |
| API key leak | Uncontrolled cost | Keep in secrets, never commit |

## 9. Open questions

1. What accuracy is acceptable to end users?
2. Who is the primary end user: an agency, a consultant, or a researcher?
3. Must it work fully offline in the field without a signal?
4. Must results follow a specific official report format?
5. What is the plan for collecting field data for validation?
