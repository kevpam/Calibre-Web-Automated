import logging
log = logging.getLogger(__name__)

NOTIFIER_REGISTRY: dict[str, type] = {}

def register(provider_key: str, klass: type):
    NOTIFIER_REGISTRY[provider_key] = klass
    log.info("Registered notifier '%s' as %s.%s", provider_key, klass.__module__, klass.__name__)

def get_notifier(provider: str):
    return NOTIFIER_REGISTRY.get((provider or "").lower())
