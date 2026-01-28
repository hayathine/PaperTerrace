import threading

from jamdict import Jamdict

# Thread-local storage for Jamdict instances
_thread_local = threading.local()


def _get_jam() -> Jamdict:
    """Get a thread-local Jamdict instance."""
    if not hasattr(_thread_local, "jam"):
        _thread_local.jam = Jamdict()
    return _thread_local.jam


def lookup_word(lemma: str) -> bool:
    """Thread-safe word lookup."""
    jam = _get_jam()
    res = jam.lookup(lemma)
    return len(res.entries) > 0


def _lookup_word_full(lemma: str):
    """Thread-safe full word lookup for explain."""
    jam = _get_jam()
    return jam.lookup(lemma)
