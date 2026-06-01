# Contributing

Thanks for considering a contribution to `wushu_motion_visualizer`.

This project is a Python-based Wushu motion skeleton visualization and training observation tool. Please keep contributions aligned with that scope.

## Ground Rules

- Keep the project positioned as a visualization and analysis aid, not an automatic scoring or medical diagnosis system.
- Do not claim precise muscle force, breathing, or biomechanical measurement unless the implementation and validation truly support it.
- Avoid large refactors unless they are discussed first.
- Do not commit local videos, generated outputs, caches, or large binary files.

## Local Setup

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Use `http://localhost:8501` or `http://127.0.0.1:8501` in the browser.

## Tests

Run:

```bash
python -m pytest
```

Tests should not require a physical camera, real video files, or a GUI.

## Pull Requests

For pull requests, please include:

- What changed
- Why it changed
- How it was tested
- Any known limitations
