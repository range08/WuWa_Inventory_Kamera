# Echo OCR design research

Research date: 2026-09-25

This document records design observations only. No source code from the projects below was copied into WuWa Inventory Kamera.

## Projects reviewed

### FrequencyManager

Repository: https://github.com/Voruzhu/FrequencyManager

Observed approach:

- Wuthering Waves Echo OCR is explicitly described as verified against real screenshots.
- The documented scanner workflow uses the individual Echo detail screen, where name, cost/main information, and substats are visible together.
- The documented OCR path is intentionally constrained to fullscreen 1920x1080.
- Unverified scanner modes are disabled rather than presented as supported.
- Game-data packages and application updates are separated from the main application lifecycle.

License observed in the repository: MIT.

Design ideas worth retaining:

- do not claim or enable a layout until it has real screenshot evidence;
- keep game-data updates separate from scanner logic;
- prefer one detail screen that exposes all required fields over reconstructing state from unrelated screens;
- make unsupported modes fail closed.

### wuwa-toolkit

Repository: https://github.com/MinhBN-dev/wuwa-toolkit

Observed approach:

- Echo OCR accepts screenshots rather than driving the game UI.
- RapidOCR is used locally as the first OCR backend.
- The project documents optional cloud-model fallbacks when local OCR produces no usable stats.

License status was not established during this audit; no code is copied or adapted.

Design ideas worth retaining:

- local OCR first;
- screenshot-only input is useful for deterministic regression fixtures and manual diagnostics;
- keep OCR extraction separate from scoring/optimization logic.

Design ideas intentionally **not** adopted:

- automatic cloud OCR fallback. This fork keeps account screenshots local and does not upload game captures to third-party AI services.

### ok-wuthering-waves / ok-ww

Repository: https://github.com/ok-oldking/ok-wuthering-waves

Observed approach:

- computer-vision / image-recognition automation using ordinary Windows interaction rather than game-memory modification;
- configurable capture backends such as Windows Graphics Capture / BitBlt;
- explicit supported-resolution policy with a 16:9 baseline;
- template/feature matching thresholds;
- display-environment checks such as HDR/night-light handling;
- feature-driven waiting/state detection is part of the surrounding automation architecture.

License status was not established during this audit; no code is copied or adapted.

Design ideas worth evaluating independently:

- expected-feature detection before/after actions;
- alternative capture backends if MSS becomes unreliable;
- explicit display-environment validation;
- wait-for-stable / feature-driven transitions rather than only fixed sleeps.

This project will not copy automation code, templates, assets, or implementation details from ok-ww. The comparison is architectural only.

### WuWaOpt

Repository: https://github.com/EMCJava/WuWaOpt

The repository currently states that it is unmaintained after Wuthering Waves 2.1. Its scanner documentation still reinforces two historical constraints also seen elsewhere: 1920x1080 and 100% Windows display scaling.

It is treated as historical context, not a current implementation reference.

## Decisions for this fork

The modernization should continue with these principles:

1. **Evidence-gated support**
   - 1920x1080 is the first live-validation target.
   - Other resolutions stay rejected until real diagnostic captures exist.

2. **Local-only OCR**
   - RapidOCR remains local.
   - No automatic upload of UID/account/game screenshots to external OCR or AI services.

3. **Screenshot-only diagnostics**
   - Keep the no-click ROI capture tool.
   - Keep the click-through live ROI overlay.
   - Build regression fixtures only from reviewed, narrowly cropped images.

4. **Fail closed**
   - Unknown/low-confidence item, weapon, and Echo inventory entries go to review artifacts.
   - Critical character state that cannot safely be skipped aborts the scan instead of fabricating a value.

5. **Transition validation next**
   - The next state-machine work should identify visual evidence for the expected screen before a click and expected screen after a click.
   - Bounded retries should be driven by observed state, not unbounded sleeps.

6. **Capture backend isolation**
   - Keep screenshot acquisition behind a narrow interface so an alternative Windows capture backend can be added later without rewriting OCR/parser code.

## License boundary

WuWa Inventory Kamera remains GPL-3.0. This research intentionally uses only public documentation and high-level behavioral observations. No external OCR implementation, templates, game assets, or source snippets were copied into this fork.
