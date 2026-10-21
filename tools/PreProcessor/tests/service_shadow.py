"""Run a HOST SUBPROCESS against a mutated service, without editing the tree.

#173's problem, and it has two gates with it. An in-memory mutant reaches only
the checks that run in this process; a headless host runs as a SUBPROCESS, so a
check that drives one — `test_case_type_roles.py`'s check 10,
`test_case_type_scale.py`'s check 10 — can only be reddened by a mutation that
is on disk when the child imports it.

Until #173 both of those mutated the HOST itself, whose own `main()` performed
the overlay, the bindings and the pre-flight. #173 deleted that orchestration in
favour of `services/case_type_apply.py`, so the mutation has to land in the
SERVICE while the host under test stays the real file. That is a strictly better
injection — it gates the host going through the service as well, since a host
that still did the work itself would not notice a mutated one — and it is why
this module exists rather than two copies of the trick.

HOW. A package holding ONE module, whose `__init__.py` appends the real
directory to its own `__path__`:

    tmp/gui/app/__init__.py           -> __path__.append(<real>/app)
    tmp/gui/app/services/__init__.py  -> __path__.append(<real>/app/services)
    tmp/gui/app/services/<name>.py    -> the mutant

so `app.services.<name>` resolves to the mutant and every other module falls
through to the real tree, keeping its own `__file__`. That last part is the
reason this is not a `copytree`: `services/paths.repo_root()` derives the repo
from `__file__`, and a wholesale copy of the 4.3 MB package moves it.

The HOST is copied VERBATIM beside that `gui/`, because it derives its import
root from its own `__file__` and inserts it at `sys.path[0]` — which is what
puts the shadow in front of the real tree even when the caller also passes the
real one on `PYTHONPATH`, as both gates' runners do.
"""
from __future__ import annotations

import os


def shadow_host(tmp: str, gui_dir: str, host_path: str, modules: dict) -> str:
    """Copy `host_path` into `tmp` over a shadow of `gui_dir`; return its path.

    `modules` maps a module name under `app.services` to the SOURCE it should
    have in the child. Everything not named falls through to the real tree.
    """
    services = os.path.join(tmp, "gui", "app", "services")
    os.makedirs(services, exist_ok=True)
    real_app = os.path.join(gui_dir, "app")
    for init, real in ((os.path.join(tmp, "gui", "app", "__init__.py"),
                        real_app),
                       (os.path.join(services, "__init__.py"),
                        os.path.join(real_app, "services"))):
        with open(init, "w", encoding="utf-8") as fh:
            fh.write("__path__.append(%r)\n" % real)
    for name, source in modules.items():
        with open(os.path.join(services, name + ".py"), "w",
                  encoding="utf-8") as fh:
            fh.write(source)
    out = os.path.join(tmp, os.path.basename(host_path))
    with open(host_path, encoding="utf-8") as fh:
        host_src = fh.read()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(host_src)
    return out
