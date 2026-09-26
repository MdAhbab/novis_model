# data/real_capture/

Dashboard `.json` exports land here, on D:, one file per download.

Do not put them in Downloads on C: - they are large (a full-size JPEG per
scene, a 768-pixel thermal frame per sample) and C: fills up.

    python scripts/ingest_capture.py            # pulls them out of Downloads

Git ignores everything in this folder except this file.
