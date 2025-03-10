import logging
import threading
from functools import wraps
from enum import Enum

LOGGER = logging.getLogger(__name__)

class CacheType(Enum):
    STREAMLIT = 1
    BOND = 2

_GLOBAL_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TYPE: CacheType = CacheType.BOND

def configure_cache(type: CacheType):
    LOGGER.info(f"Configuring cache type: {type}")
    global _CACHE_TYPE
    _CACHE_TYPE = type

def bond_cache(func):
    """A decorator that provides a simple, thread-safe, global cache."""
    if _CACHE_TYPE == CacheType.STREAMLIT:        
        LOGGER.debug("Using Streamlit cache")
        import streamlit as st

        @st.cache_resource
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper  # 🔥 This was missing!


    elif _CACHE_TYPE == CacheType.BOND:
        LOGGER.debug("Using Bond cache")

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (func, args, frozenset(kwargs.items()))  

            with _CACHE_LOCK:
                if key in _GLOBAL_CACHE:
                    return _GLOBAL_CACHE[key]  

            result = func(*args, **kwargs)  

            with _CACHE_LOCK:
                _GLOBAL_CACHE[key] = result 

            return result

        return wrapper
    else:
        raise ValueError(f"Unknown cache type: {_CACHE_TYPE}")

def bond_cache_clear():
    with _CACHE_LOCK:
        if _CACHE_TYPE == CacheType.STREAMLIT:
            import streamlit as st
            st.cache_resource.clear()
        else:
            _GLOBAL_CACHE.clear()