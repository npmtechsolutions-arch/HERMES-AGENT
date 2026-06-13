# AI OFFICE ASSISTANT — CONDITIONAL DOCUMENT
**Business Rules, Decision Conditions, Edge Cases & System Behaviors**
**Version 1.0**

This document defines every significant IF/THEN condition governing system behavior. Format: **Condition → System Behavior**. Rule IDs are referenced by the Workflow Engine, Approval Chains, and Self-Healing Agent.

---

## 1. VOICE INPUT CONDITIONS (VC)

| ID | Condition | Behavior |
|---|---|---|
| VC-01 | STT confidence ≥ 0.85 | Execute intent directly |
| VC-02 | STT confidence 0.60–0.84 | Voice confirm: "Did you mean…?" with top candidate |
| VC-03 | STT confidence < 0.60 | "I didn't catch that" + show top-3 transcript candidates on screen |
| VC-04 | Intent matched but parameters missing | Slot-filling dialog (max 3 follow-up questions, then offer screen form) |
| VC-05 | No intent match | Speak nearest capability + open command palette |
| VC-06 | Sensitive action (money, send-external, delete) regardless of confidence | Mandatory explicit voice confirmation ("yes"/"confirm") — never inferred |
| VC-07 | User barges in during TTS | Stop TTS within 200 ms; treat new speech as command |
| VC-08 | Multiple speakers detected (enterprise) | Use voice-print; if unidentified speaker issues privileged command → refuse + log |
| VC-09 | Wake word triggered ≥5 times in 60 s with no command | Suggest sensitivity adjustment; offer push-to-talk |
| VC-10 | Mic unavailable / permission denied | Banner + fallback to keyboard-first mode; all features remain usable |
| VC-11 | Language detected ≠ session locale | Auto-switch STT model if supported; else respond in session language and note limitation |
| VC-12 | Background noise level > threshold during dictation | Pause + "It's noisy — switch to push-to-talk?" |
| VC-13 | Do-Not-Disturb window active | Suppress proactive voice; queue notifications as visual badges; urgent-class items may break through if user enabled override |
| VC-14 | Continuous-listening session idle > configurable timeout | Auto-return to wake-word mode + soft chime |

---

## 2. TASK & ORCHESTRATION CONDITIONS (TC)

| ID | Condition | Behavior |
|---|---|---|
| TC-01 | Task has no deadline | Default priority = Normal; CEO Agent schedules by queue order |
| TC-02 | Deadline < estimated completion time | Voice alert with options: parallelize, simplify scope, extend deadline |
| TC-03 | No agent has required skill | CEO Agent proposes: hire new agent, install marketplace pack, or human handles |
| TC-04 | Two agents equally capable | Assign by lowest utilization, then highest success-rate KPI |
| TC-05 | Assigned agent status = Working and new task priority = Urgent | Offer interrupt-or-queue choice; interrupt checkpoints current task |
| TC-06 | Task blocked on dependency > SLA hours | Auto-escalate to reporting manager agent; notify user at 2× SLA |
| TC-07 | Subtask fails after self-healing exhausts retries | Mark task Escalated; CEO Agent re-plans around failure or surfaces to human |
| TC-08 | Task result confidence flagged low by executing agent | Route through Reviewing state (peer/manager agent check) before Completed |
| TC-09 | Identical task pattern executed ≥3 times manually | Proactive suggestion: "Want me to make this a scheduled workflow?" |
| TC-10 | Task touches entity marked Confidential in Knowledge Graph | Restrict to agents with Confidential clearance; suppress details in bus messages |
| TC-11 | User cancels mid-execution | Graceful stop: finish atomic step, roll back where supported, log partial state |
| TC-12 | Recurring task fails 2 consecutive runs | Pause schedule + notify user (voice + visual) rather than failing silently forever |

---

## 3. APPROVAL CHAIN CONDITIONS (AC)

| ID | Condition | Behavior |
|---|---|---|
| AC-01 | Expense / payment ≤ agent's delegated limit | Specialist auto-approves; logged |
| AC-02 | Amount > specialist limit ≤ manager limit | Manager Agent reviews with rationale requirement |
| AC-03 | Amount > manager limit ≤ CEO Agent limit | CEO Agent reviews; may auto-approve if matches precedent in Operational Memory |
| AC-04 | Amount > CEO Agent limit OR no precedent | Human approval mandatory (voice notification) |
| AC-05 | Outbound message to a NEW external contact | Human approval required (anti-mistake/anti-spam) until contact whitelisted |
| AC-06 | Bulk action ≥ N records (default 50) | Human approval + dry-run preview |
| AC-07 | Destructive op (delete data, cancel order, unsubscribe) | Human approval; no AI tier may auto-approve |
| AC-08 | Approval pending > timeout (default 4 h) | Escalate one tier up; final tier → reminder schedule (4h, 24h) |
| AC-09 | Approver = requester (same agent) | Invalid; route to next tier (segregation of duties) |
| AC-10 | Human says "Approve all from this agent today" | Create temporary delegation rule, expiring midnight, logged |
| AC-11 | Rejected request resubmitted unchanged | Auto-reject with reference to prior decision |
| AC-12 | Enterprise: approver lacks department access | Skip to next eligible approver in chain |

---

## 4. MEMORY & KNOWLEDGE CONDITIONS (MC)

| ID | Condition | Behavior |
|---|---|---|
| MC-01 | Ingested document duplicates existing (hash match) | Skip + link reference; notify |
| MC-02 | Ingested content conflicts with existing knowledge (e.g., two different GST numbers for same vendor) | Flag conflict in Knowledge Graph; ask user which is current; keep history |
| MC-03 | Memory item not accessed in N months (configurable) | Move to cold tier; still searchable; excluded from default agent context |
| MC-04 | User says "Forget X" | Soft-delete with 30-day recovery window, then purge; audit entry (content-free) |
| MC-05 | Agent requests memory outside its scope | Deny + log; agent may file access request → approval chain |
| MC-06 | OCR confidence < threshold on ingested scan | Mark low-confidence; require human verification before agents cite it |
| MC-07 | Knowledge Graph entity referenced by voice is ambiguous ("Sharma") | Disambiguation by recency + relationship strength; ask if still ambiguous |
| MC-08 | PII detected in ingested content | Tag as PII; restrict to clearance-holding agents; exclude from any opt-in cloud calls |
| MC-09 | Storage usage > 85% of allocated | Voice + visual warning; propose cold-tier compression or archive export |

---

## 5. LLM & COMPUTE CONDITIONS (LC)

| ID | Condition | Behavior |
|---|---|---|
| LC-01 | Requested model exceeds free VRAM | GPU Manager: unload least-recently-used model, or offer quantized variant |
| LC-02 | Voice pipeline latency at risk (VRAM pressure) | Voice models have reserved allocation — never evicted; task models yield |
| LC-03 | Task complexity score low (classification, extraction) | Route to small model (e.g., Phi/Gemma small) automatically |
| LC-04 | Task complexity high (planning, legal drafting) | Route to largest available model; if quality tier unavailable locally → offer BYO-cloud (explicit consent) |
| LC-05 | Model output fails schema/validation 2× | Retry with stricter prompt; 3rd failure → escalate model tier or to human |
| LC-06 | CPU-only machine detected | Default to small quantized models; disable parallel multi-agent inference; set expectation in UX |
| LC-07 | Model download interrupted | Resume from checkpoint; verify checksum before activation |
| LC-08 | Multi-node network available | Place models per node capability; route inference to least-loaded capable node |
| LC-09 | Thermal/battery constraint (laptop on battery) | Power-saver: reduce concurrency, defer non-urgent scheduled tasks |

---

## 6. COMMUNICATION & CALL CONDITIONS (CC)

| ID | Condition | Behavior |
|---|---|---|
| CC-01 | Inbound message classified Urgent | Proactive voice alert (respecting VC-13) |
| CC-02 | Auto-reply rule matches but message contains a question outside knowledge | Don't auto-send; draft + flag for human |
| CC-03 | Outbound email contains amounts/dates pulled from memory | Agent must cite source record; mismatch with source → block send |
| CC-04 | Recipient previously opted out | Block send on that channel; suggest alternative |
| CC-05 | Inbound call: caller matched in CRM | Personalized greeting + context loaded |
| CC-06 | Inbound call: negative sentiment ≥ threshold OR "human" requested | Warm transfer + spoken summary to human; if unavailable → apology + callback task |
| CC-07 | Outbound call window outside permitted hours (per region) | Defer to next permitted window |
| CC-08 | Call recording where two-party consent required | Play disclosure before conversation; if declined → no recording, notes only |
| CC-09 | Same external thread receives ≥3 AI replies without resolution | Stop auto-replying; escalate to human |
| CC-10 | Channel API rate limit reached | Queue with backoff; notify if SLA at risk |

---

## 7. SELF-HEALING CONDITIONS (SH)

| ID | Condition | Behavior |
|---|---|---|
| SH-01 | Error class = transient (timeout, 5xx, network blip) | Retry ×3, exponential backoff (5s/30s/2m) |
| SH-02 | Error class = credential (401/403, expired token) | Pause dependent tasks; Vault re-auth voice prompt; resume on success |
| SH-03 | Error class = config (schema change, missing field, renamed selector) | Generate remediation proposal; apply only after approval (AC chain) |
| SH-04 | Error class = logic (bad plan, contradiction) | Escalate to CEO Agent re-plan; then human |
| SH-05 | Same error signature ≥3 occurrences in 7 days | Create incident pattern; pre-emptive check added before future runs |
| SH-06 | Browser automation selector broken | Attempt semantic re-location of element; if found → propose selector update |
| SH-07 | Healing action itself fails | Never loop: max 1 healing attempt per failure; escalate |
| SH-08 | Workflow paused by healing > 24 h | Daily voice reminder until resolved or cancelled |

---

## 8. SECURITY & ACCESS CONDITIONS (SC)

| ID | Condition | Behavior |
|---|---|---|
| SC-01 | App start | Verify DB integrity + vault lock state; require unlock (OS auth / passphrase / voice-print where enabled) |
| SC-02 | Privileged voice command + speaker unverified (multi-user) | Refuse politely; offer authentication; log attempt |
| SC-03 | Plugin requests new permission at runtime | Block; permissions only grantable at install/update via consent screen |
| SC-04 | Marketplace package signature invalid | Refuse install |
| SC-05 | Agent attempts tool not in its grant list | Deny + audit; suggest permission request flow |
| SC-06 | Failed unlock ≥5 attempts | Lockout with increasing delay; notify admin (enterprise) |
| SC-07 | Audit log write fails | Halt the action that required it (no unaudited privileged actions) |
| SC-08 | Offline Enterprise Mode active | Hard-disable all WAN egress at app network layer; only LAN node traffic permitted |
| SC-09 | Export of memory/backup requested | Encrypt export; require explicit confirmation + audit |
| SC-10 | New device pairing request (Agent Network) | Require admin role + physical code entry; mutual TLS; reject on cert mismatch |

---

## 9. SCHEDULING CONDITIONS (SD)

| ID | Condition | Behavior |
|---|---|---|
| SD-01 | Machine asleep/off at scheduled time | Run-on-wake policy (default) or skip, per workflow setting; notify result |
| SD-02 | Two workflows contend for same exclusive resource | Priority order; loser queued; both logged |
| SD-03 | CRON expression invalid | Reject at save with spoken explanation + suggested fix |
| SD-04 | Timezone/DST shift | Schedules stored as local-time + zone; recompute on shift |
| SD-05 | Event trigger storms (≥X events/min) | Debounce/batch per workflow config; alert if sustained |

---

## 10. ENTERPRISE & MULTI-USER CONDITIONS (EC)

| ID | Condition | Behavior |
|---|---|---|
| EC-01 | User queries data of another department (isolation on) | Deny; show "request access" path |
| EC-02 | Shared memory write by two users conflicts | Last-write-wins + version history retained |
| EC-03 | Admin disables a user | Their sessions end; their personal agents pause; reassignment wizard offered |
| EC-04 | License seat count exceeded | New activations blocked; existing unaffected; admin alert |
| EC-05 | Node leaves network mid-task | Tasks checkpointed and re-routed; if non-resumable → restart with notice |

---

## 11. DEFAULT THRESHOLDS (CONFIGURABLE)

| Parameter | Default |
|---|---|
| STT auto-execute confidence | 0.85 |
| Specialist auto-approval spend limit | ₹5,000 / $60 |
| Manager agent approval limit | ₹25,000 / $300 |
| CEO Agent approval limit | ₹50,000 / $600 |
| Bulk-action approval threshold | 50 records |
| Approval timeout before escalation | 4 hours |
| Self-heal retry count / backoff | 3 / 5s–2m exponential |
| Cold-memory age | 6 months |
| Forget-recovery window | 30 days |
| DND default window | 21:00–08:00 |

---

# PART B — SAAS CONDITIONS (Cloud Plane)

## 12. SUBSCRIPTION & ENTITLEMENT CONDITIONS (SB)
| ID | Condition | Behavior |
|---|---|---|
| SB-01 | Trial expires, no payment method | Soft-lock desktop (agents paused, read-only); data intact; export allowed |
| SB-02 | Action exceeds plan limit | Block action + upsell (voice/visual); offer archive alternative |
| SB-03 | Downgrade leaves excess resources | Excess agents/workflows auto-Archived (read-only), user picks which |
| SB-04 | Upgrade mid-cycle | Prorated charge; entitlements apply immediately |
| SB-05 | Entitlement cache older than grace (default 7 days, Enterprise offline-license exempt) | Warn at 80%; soft-lock after expiry until heartbeat succeeds |
| SB-06 | Device count exceeded on activation | Show device list; require deactivation of one |
| SB-07 | Seat removed from team member | Their desktop soft-locks at next heartbeat; personal data export offered |
| SB-08 | Plan flag disables a feature in active use (admin change) | Feature enters read-only; nothing deleted; notice shown |

## 13. PAYMENT & BILLING CONDITIONS (PB)
| ID | Condition | Behavior |
|---|---|---|
| PB-01 | Webhook payment_failed | Dunning: retries day 1/3/7 + emails; 7-day full-function grace; then SB-01 soft-lock |
| PB-02 | Payment recovered | Instant reactivation; audit entry |
| PB-03 | Refund requested ≤ 14 days (policy) | Support Admin initiates → Finance Admin approves (four-eyes) → gateway refund → plan revoked |
| PB-04 | Chargeback received | Auto-suspend tenant pending review; admin queue item |
| PB-05 | Tax region detected (GST/VAT) | Apply correct tax line + invoice format |
| PB-06 | Gateway webhook signature invalid | Reject + alert; never mutate state |
| PB-07 | Duplicate webhook (idempotency key seen) | Ignore safely |

## 14. PRODUCT ADMIN CONDITIONS (PA)
| ID | Condition | Behavior |
|---|---|---|
| PA-01 | Destructive admin action (delete tenant, mass refund, force update) | Second-admin approval required (four-eyes) |
| PA-02 | Support impersonation requested | Requires explicit user consent token; session time-boxed; banner shown; fully audited |
| PA-03 | Common config marked "locked" | Desktop cannot override; UI shows "managed by provider" |
| PA-04 | Config canary error rate > threshold | Auto-halt rollout; rollback offered |
| PA-05 | Release crash rate > threshold during staged rollout | Auto-pause rollout; alert |
| PA-06 | Marketplace package fails signature/security scan | Reject; publisher notified |
| PA-07 | Admin role lacks scope for action | Deny + audit (admin RBAC mirrors SC rules) |
| PA-08 | Tenant flagged for abuse (e.g., spam via comms channels) | Throttle → review queue → suspend if confirmed |

## 15. DATA-BOUNDARY CONDITIONS (DB)
| ID | Condition | Behavior |
|---|---|---|
| DB-01 | Any payload from desktop to cloud contains business-data fields | Schema validation rejects; incident logged (privacy invariant) |
| DB-02 | Telemetry opt-in OFF (default) | Only license heartbeats + crash signatures (no content) transmitted |
| DB-03 | Account deletion requested | Cloud PII purged ≤ 30 days; local data untouched (user's machine); certificates revoked |
