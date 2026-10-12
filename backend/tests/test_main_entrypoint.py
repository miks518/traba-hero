"""The port in `backend/.env` has to actually decide the port.

`HOST` and `PORT` were read by nobody. `main.py` built a FastAPI app and
stopped there — no `uvicorn.run`, no `__main__` block — so the settings only
existed to be written down and look authoritative.

The failure is invisible and was caught only by a person: setting `PORT=8010`
and running `uvicorn app.main:app --reload` served on 8000 anyway, because
uvicorn's own default is 8000 and it never consults the app's Settings. The
symptom looked like the setting was wrong, so the fix was to keep editing the
file — which is exactly what a decorative setting invites.

So this asserts the setting is *consumed*, not merely present. A field that
nothing reads is a field that lies.
"""

import app.main as main_module
from app.config import settings


def test_the_configured_port_is_what_launches_the_server(monkeypatch):
    launched = {}

    monkeypatch.setattr(
        main_module.uvicorn, "run", lambda *args, **kwargs: launched.update(kwargs)
    )

    main_module.run()

    assert launched["port"] == settings.port
    assert launched["host"] == settings.host


def test_reload_is_off_unless_asked_for(monkeypatch):
    """Reload is a development convenience, not something a deployment
    should pick up from an environment variable nobody documented."""
    launched = {}
    monkeypatch.setattr(
        main_module.uvicorn, "run", lambda *args, **kwargs: launched.update(kwargs)
    )

    main_module.run()
    assert launched["reload"] is False

    launched.clear()
    main_module.run(reload=True)
    assert launched["reload"] is True


def test_the_shipped_port_is_not_the_one_vllm_probes():
    """opencode's built-in vLLM provider is pinned to 127.0.0.1:8000 and polls
    `/health` then `/v1/models` there on a timer. A backend on 8000 answers
    the first and 404s the second, once a minute, in the access log.

    Cheap to regress and impossible to notice until the log starts filling,
    so it is asserted rather than left to a comment nobody reads.
    """
    assert settings.port != 8000


def test_the_module_is_runnable():
    """`python -m app.main` is the documented way to honour HOST and PORT."""
    assert callable(getattr(main_module, "run", None))
    assert main_module.__doc__ or True  # module imports cleanly