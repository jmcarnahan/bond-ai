import logging 
LOGGER = logging.getLogger(__name__)

from bondable.bond.cache import configure_cache, bond_cache_clear, bond_cache, CacheType
import pytest



count: int = 0

class TestCache:

  @pytest.fixture
  def setup(self):
    yield
    global count
    count = 0
    bond_cache_clear()

  def test_count_bond(self, setup):
    configure_cache(CacheType.BOND)

    @bond_cache
    def increment():
        global count
        count += 1
        return count

    assert increment() == 1
    assert increment() == 1
    assert increment() == 1

  def test_count_streamlit(self, setup):
    configure_cache(CacheType.STREAMLIT)

    @bond_cache
    def increment():
        global count
        count += 1
        return count

    assert increment() == 1
    assert increment() == 1
    assert increment() == 1

  def test_count_bond_class(self, setup):
    configure_cache(CacheType.BOND)

    class MyClass:

      @classmethod
      @bond_cache
      def increment(cls):
          global count
          count += 1
          return count

    assert MyClass.increment() == 1
    assert MyClass.increment() == 1
    assert MyClass.increment() == 1

  def test_count_streamlit_class(self, setup):
    configure_cache(CacheType.STREAMLIT)

    class MyClass:

      @classmethod
      @bond_cache
      def increment(cls):
          global count
          count += 1
          return count

    assert MyClass.increment() == 1
    assert MyClass.increment() == 1
    assert MyClass.increment() == 1