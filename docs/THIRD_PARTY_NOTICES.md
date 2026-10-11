# THIRD_PARTY_NOTICES

This repository's new `muscle_analysis/` feature was implemented as a lightweight, local heuristic visualizer.

No source files were copied from OpenCap, OpenCap API, OpenCap Processing, or OpenSim.
Only high-level product ideas and terminology boundaries were consulted when deciding how to keep this feature lightweight and non-medical.

Referenced projects and licenses checked during design:

1. OpenCap Core / Processing
   - Repository: https://github.com/stanfordnmbl/opencap-core
   - Related repository: https://github.com/stanfordnmbl/opencap-processing
   - License: Apache-2.0
   - Usage in this project: conceptual inspiration only; no source code copied.

2. OpenCap API
   - Repository: https://github.com/stanfordnmbl/opencap-api
   - License: Apache-2.0
   - Usage in this project: conceptual inspiration only; no source code copied.

3. OpenSim Core
   - Repository: https://github.com/opensim-org/opensim-core
   - License: Apache-2.0
   - Usage in this project: future integration target only; no source code copied.

4. MediaPipe
   - Repository: https://github.com/google-ai-edge/mediapipe
   - License: Apache-2.0
   - Usage in this project: already used as the pose-estimation backend through the Python package dependency.

Notes:

- The current muscle participation overlay is a heuristic visualization built on pose landmarks and kinematic features.
- It does not implement OpenSim inverse dynamics.
- It does not estimate EMG, force plate data, or medical muscle activation.
