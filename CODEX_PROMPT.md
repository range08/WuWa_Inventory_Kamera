# Codex implementation prompt

You are modernizing a fork of `Psycho-Marcus/WuWa_Inventory_Kamera`.

Read `todo.md` in full before changing anything. Treat it as the authoritative implementation checklist.

1. Inspect the entire repository and current git status before modifying files.
2. Identify and record the upstream baseline commit.
3. Work through `todo.md` in order.
4. Verify every checked item by inspection, automated test, or documented manual test.
5. Make small cohesive commits.
6. Preserve GPL-3.0 and upstream attribution.
7. Do not introduce memory reading, DLL injection, packet interception, anti-cheat bypasses, process tampering, or credential logging.
8. Use ordinary screen capture/OCR and ordinary user-level input.
9. Never silently invent OCR values.
10. Keep legacy export formats compatible unless a versioned migration is intentional.
11. Target Global 3.6.x initially, but make the data updater suitable for 3.7+.
12. Prioritize 1920x1080 fullscreen.
13. Explicitly support/test Korean and English.
14. Replace obsolete Dimbreath data coupling with a provider abstraction; inspect the current data source and licensing before implementation.
15. Do not use remote file size alone for update detection.
16. Add tests before broad refactors where feasible.
17. Fix the known `scrapeSkills()` cache-key defect early.
18. Do not mark ROI tasks complete without current-game screenshots.
19. Never expose or persist Kuro launcher OAuth credentials.
20. At each phase end, run applicable tests, inspect diff, update only verified checkboxes, and record blockers.

Start with Phase 0 and Phase 1, then continue autonomously as far as the environment permits.
