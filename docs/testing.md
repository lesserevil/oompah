# Running the test suite

Use `make test` for the project gate. It runs pytest through a bounded
pytest-xdist pool and defaults to four workers:

```bash
make test
```

Set `OOMPAH_PYTEST_WORKERS` in `.env` to an integer from 1 through 16 when the
host needs a different bound. The Makefile also accepts a one-run shell
override:

```bash
OOMPAH_PYTEST_WORKERS=8 make test
```

Do not set the value to the machine's CPU count without measuring memory,
storage, and subprocess pressure. Each worker receives a private HOME, temp,
and XDG cache tree under `OOMPAH_TEMP_ROOT`; the run tree is removed when
pytest exits. Tests that own server subprocesses or process-global ports are
kept together on one worker.

For ordering, isolation, or failure-output diagnosis, use the deterministic
serial fallback:

```bash
make test-serial
```

Both targets preserve pytest's exit status. A failed parallel run should be
reproduced with `make test-serial` before attributing it to worker scheduling.
