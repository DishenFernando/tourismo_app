# Tourismo Unicode Display Repair — Pre-Phase-5

## Symptom
The vendor dashboard displays `Â·` instead of `·`, `âœ“` instead of `✓`, and `â†’` instead of `→`. These are mojibake: UTF-8 bytes interpreted as Windows-1252 text. This is **not** a translation setting or a PostgreSQL character-set change.

## Safe procedure (Windows PowerShell)
1. Back up local work (or commit to Git).
2. Extract only the changed/new files from the update ZIP, or apply the add-only patch. Do not overwrite `.env` or `infra/compose.yaml`.
3. Run a read-only audit:

```powershell
cd D:\Tourismo\Tourismo
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/project" -w /project python:3.12-slim python scripts/repair-tourismo-text.py --check
```

If the audit reports corrupted files, fix them with:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/project" -w /project python:3.12-slim python scripts/repair-tourismo-text.py --fix
```

It creates one `.before-encoding-fix` backup per altered source file. The command never touches `.env`, Docker Compose, or databases. The algorithm only reverses recognizable, fully reversible text corruption. If a character is already replaced with `�`, manual inspection is required.

4. Verify corrected source and run focused tests:

```powershell
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/project" -w /project python:3.12-slim python scripts/test-tourismo-encoding.py
docker run --rm --mount "type=bind,source=$((Get-Location).Path),target=/project" -w /project/apps/web node:22-alpine node scripts/check-encoding.mjs
```

5. Rebuild and check the frontend bundle:

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -ExecutionPolicy Bypass -File .\scripts\verify-pre-phase5-with-utf8.ps1
```

6. In Edge/Chrome, use **Ctrl+Shift+R** after the successful rebuild, or open an InPrivate window.

### If the source audit reports zero issues but the browser still shows broken text
Inspect the **actual served JS bundle**, rather than repeatedly editing clean source:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec -T app python -c "from pathlib import Path; p=Path('/app/web-dist/assets'); files=list(p.glob('*.js')); bad=[x.name for x in files if any(y in x.read_text('utf-8') for y in ['Â·','âœ“','â†’'])]; print('JS assets:',len(files),'corrupted:',bad)"
```

If the bundle is corrupted while the source is clean, do a clean rebuild (`docker compose --env-file .env -f infra/compose.yaml build --no-cache app`) and restart. If both source and bundle are clean, clear browser cache and check the Network response/charset. Do not run `docker compose down -v`.

## Developer safeguards
- `apps/web/index.html` already declares `<meta charset="UTF-8">`.
- `npm run build` now checks the frontend source for invalid UTF-8 and recognizable mojibake before TypeScript and Vite compile.
- `scripts/verify-pre-phase5.ps1` is unchanged; `scripts/verify-pre-phase5-with-utf8.ps1` adds extra encoding checks.
- No database migrations or application authorization changes.
