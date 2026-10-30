# Vercel Management API migration (Windows Agent)

## Production endpoint and secret migration

The new default is `https://windows-agent-management.vercel.app/api/agent`. On loading the DPAPI-protected `manager_secret.bin`, the Agent recognizes only the retired `windows-agent-management-cloudflare.soheylfriend.workers.dev` host as a migration source, replaces it with the Vercel URL, and atomically re-seals the existing JSON with Windows DPAPI. It logs a one-time notice without printing the key. The current key is retained encrypted so the new API can validate it; HTTP 401 is shown as **کلید نامعتبر**, HTTP 403 as **دسترسی ناکافی**. Neither causes a rapid retry. If the key is rejected, create a new Agent key in the management site and enter it in the local UI. No legacy URL is used for a new request.

Only `heartbeat:write`, `commands:read`, `events:write`, `results:write`, `artifacts:write`, and `automations:read` are expected. A 403 log names the operation and required scope, never the key.

## Heartbeat transition

Heartbeat advertises `command_plane`, `database_automations`, `vercel_blob_screenshot_upload`, and `google_drive_artifacts: false`; `d1_automations` remains only as a temporary compatibility alias. The reported state has `manager_base: "vercel"` and `drive: false`. `r2_screenshot_upload` is not advertised. Heartbeat timestamps remain UTC ISO; the local UI continues to render Tehran/Jalali time.

## Screenshot path

The Agent never contacts Vercel Blob directly. For command screenshots, it captures into `%LOCALAPPDATA%\\Windows-Agent\\screenshot_uploads\\<executionId>`, normalizes PNG/JPEG locally to below 3.8 MB (hard ceiling 4 MiB), writes the outbox manifest atomically, and uploads from a background network worker to `POST /screenshots` with Bearer Agent Key and multipart fields. It accepts success only for HTTP 201, JSON `ok: true`, a nonempty `screenshot.id`, and a relative `/api/screenshots/...` `contentUrl`. Raw Blob URLs are neither extracted nor stored.

The outbox has no credentials. It persists across restart and retries transient failures at 5, 15, 30, then 60 seconds. HTTP 401/403 blocks queued items until the locally configured key changes; 413 causes one additional local reduction attempt, never an endless retry. The server's Agent/command/stage/SHA-256 deduplication handles the crash window after server success. Successful image bytes are deleted locally after the success manifest is atomically persisted. Failed/pending images stay in LocalAppData for recovery/inspection; cancellation removes queued (not in-flight) images for that command. Upload failure is a warning and does not repeat Arena interaction.

Events include `screenshot_captured`, `screenshot_normalized`, `screenshot_upload_queued`, `screenshot_upload_started`, `screenshot_upload_succeeded`, `screenshot_upload_retry_scheduled`, or `screenshot_upload_failed_permanent`, with command/execution/stage, timestamp, size, short SHA-256, attempt, and (on success) screenshot ID. They never contain image bytes, Bearer credentials, cookies, Database URL, or raw Blob URL.

## Google Drive retirement

New screenshots and reports resolve only beneath `%LOCALAPPDATA%\\Windows-Agent`. The legacy Drive control transport is no longer started by `manager_client.start`; there are no new Drive control-file writes from the active Agent. Existing Drive files remain historical and are not read for screenshots/reports. Command events and result payloads stay on the authenticated Management API. Screenshot metadata is no longer posted to `/commands/{commandId}/artifacts` and the client no longer creates `driveFileId`/`driveUrl`.

The separate, historical `drive_control_transport.py` and its isolated unit tests remain in source for reference only; production startup does not import/start that transport.

## Local validation boundary

Cross-platform tests can validate URL migration logic, multipart construction, response acceptance, retry/backoff, persistence, dedupe, 401/403, 413, and cancellation behavior with mocked HTTP. They cannot prove production key scopes, Vercel/Prisma persistence, actual Blob storage/deletion, gallery rendering, or no-write behavior in the deployed site. The Windows-specific restart, real capture, process tree, and LocalAppData/DPAPI tests must be run on the target Windows installation. Do not report the acceptance plan as complete without those live tests.
