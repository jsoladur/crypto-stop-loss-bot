from __future__ import annotations

from crypto_trailing_stop.config.application_container import ApplicationContainer

_application_container: ApplicationContainer | None = None


def get_application_container() -> ApplicationContainer:
    global _application_container
    if _application_container is None:
        _application_container = ApplicationContainer()
        _application_container.check_dependencies()
    return _application_container
