# Emergency stop-all control

Windows Agent advertises `capabilities.emergency_stop_all` in authenticated Heartbeats. A Heartbeat response may carry an `emergencyControl` object; the independent Heartbeat worker dispatches `stop_all_executions` to a bounded background worker rather than the normal command-claim queue.

The control ID and result are persisted in `%LOCALAPPDATA%\Windows-Agent\emergency_control_state.json`. The file contains no Agent Key. Repeated IDs already processing are ignored; completed IDs are not re-executed; a saved result whose POST failed is retried without repeating the stop operation. While a control is pending, normal Command claims are gated.

The Agent first sets local cancellation, pauses background scheduling without changing the Manual/Automatic setting, requests stop for registered executions, and waits for terminal registry state, the claim worker, and marker-verified owned PIDs. The result is `succeeded` only when the active registry is empty and no owned PID or unresolved PID remains. An empty registry is explicitly reported as checked. Unknown/unverifiable PIDs produce `failed`, never a false success.

The result endpoint must be a same-origin path exactly matching `/api/agent/controls/{controlId}`; the authenticated Agent Key is never sent to a different origin. Results include `verified`, `requested`, `stopped`, `failed`, `registryActiveCount`, `activeExecutionIds`, `remainingPids`, and a Persian status message.

## Acceptance boundary

Cross-platform unit tests cover capability advertisement, endpoint validation, duplicate-control idempotency, result-post retry, empty-registry verification, and conservative failure when a process start marker is unavailable. They do **not** replace the required real-Windows tests for foreground/background child-process termination, timing, manual/automatic behavior, WebView status, and restart recovery. Do not claim a real Windows stop or a Cloudflare/D1 result until those tests have actually run.
