# Roadmap

This roadmap lists realistic maintenance and feature directions for `wushu_motion_visualizer`.

The project remains focused on Wushu motion skeleton visualization and training observation. It does not aim to become an automatic scoring, medical diagnosis, or precise biomechanical measurement system without appropriate validation.

## Near Term

- Improve error handling for unreadable videos, missing camera devices, and export failures.
- Add more unit tests for pure analysis functions.
- Keep README and UI wording aligned with the project's actual capabilities.
- Improve browser playback reliability for generated videos.
- Add small examples that do not require real training videos.

## Medium Term

- Add a lightweight task history view for completed video analyses.
- Improve trajectory and peak-time visualizations.
- Add clearer status messages for long-running video processing.
- Separate large Streamlit page functions into smaller modules when needed.
- Document cloud deployment limitations more clearly.

## Future Exploration

- Browser-based camera capture for public web deployments.
- Optional background job queue for longer video analyses.
- Better kinematic-chain timing visualizations.
- Future OpenSim or OpenCap adapter experiments, clearly marked as optional and not enabled by default.

## Out of Scope for Now

- Automatic Wushu action scoring.
- Claims of precise muscle force, breathing, or medical state recognition.
- Real-time multi-user browser camera analysis on the current local-camera architecture.
- Large model training or custom pose-estimation training.
