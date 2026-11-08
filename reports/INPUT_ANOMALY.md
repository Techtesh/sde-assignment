# Retained recovery-reference anomaly

The first added-step matrix (`89c55ef`) failed its mid-ingest comparison. Its
reference schema was `steps567_dev_clean_090fc2`; the restarted schema was
`steps567_dev_mid_ingest_b8f176`. This was not accepted as passing evidence.

A comparison of our own stored events found one difference: event **183742**
had type/kind `ball` in the reference store and `call` in the restarted store.
It was an unanswered historical call. Both stores had 297,040 total events,
but the reference had one fewer call counter and an extra non-call audit entry.
Historical dry-run counts also differed, explaining the proposal fingerprints.
No simulator source or hidden run files were read to diagnose it.

The source of this one-record anomaly was not established. We do not attribute
it to a specific service, edit, parser or hardware fault. The exact comparison
was right to fail; two runs with different stored input cannot demonstrate
deterministic recovery. The retained reference signature is
[steps567_crash_invalid_reference.json](./steps567_crash_invalid_reference.json).
The corresponding grade is archived as
[steps567_public01_invalid_reference.md](./steps567_public01_invalid_reference.md),
not used as the final grade.

`3d83779` adds a trust-boundary check for the five event types documented by the
API. A misspelling now raises an error and rolls back the complete chunk rather
than silently excluding a call from metrics. The focused regression proves that
events and the chunk checkpoint remain uncommitted. This prevents malformed
incoming types; it is not a claim to protect against arbitrary later database
tampering or hardware corruption.

The same commit fixes an independently reproduced QA issue: unrelated voice
edits previously reset prompt-alarm persistence. Prompt alarms now retain the
streak while prompt/cohort definitions are unchanged, and reset when either changes.
The final matrix is run from fresh worlds and recorded separately in
[steps567_crash_final.json](./steps567_crash_final.json).
