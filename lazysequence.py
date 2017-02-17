from collections import Sequence, Callable, deque
from weakref import WeakValueDictionary

def id_func(x):
    return x

class LazySequence(Sequence):
    """ A Sequence that lazily calculates values when needed
    based on an underlying Sequence of values and a map function.
    LazySequences can be composed, sliced, copied, and they
    maintain a cache of both recently used values and all other
    values that have not yet been garbage collected.
    """
    _ref_lru = deque(maxlen=10000)

    def __init__(self, seq=(), map_func=None):
        if map_func is not None and not isinstance(map_func, Callable):
            raise ValueError('LazySequence: map_func must be callable.')

        self._map_funcs = []
        if isinstance(seq, LazySequence):
            self._base_seq = seq._base_seq
            self._base_range = seq._base_range
            self._weakref_cache = WeakValueDictionary()

            self._map_funcs.extend(seq._map_funcs)
            if map_func is not None:
                self._map_funcs.append(map_func)

        elif isinstance(seq, Sequence):
            self._base_seq = seq
            self._base_range = range(len(seq))
            self._weakref_cache = WeakValueDictionary()

            if map_func is None:
                map_func = id_func
            self._map_funcs.append(map_func)

        else:
            raise ValueError('LazySequence: seq must be a true sequence.')

    def __len__(self):
        return len(self._base_range)

    def _apply_maps(self, val):
        for m in self._map_funcs:
            val = m(val)
        return val

    def __getitem__(self, index):
        if isinstance(index, slice):
            sub = LazySequence(self)
            sub._base_range = self._base_range[index]
            return sub
        else:
            ca = self._weakref_cache
            item = ca[index] if index in ca else None

            if item is None:
                item = self._apply_maps(self._base_seq[self._base_range[index]])

                # Only objects with a `__weakref__` attribute can
                # receive a weak reference.
                if hasattr(item, '__weakref__'):
                    self._weakref_cache[index] = item
                    # Guarantee at least one strong reference for
                    # the `n` most recently cached items.
                    self._ref_lru.append(item)

            return item

    @property
    def base_sequence(self):
        return self._base_seq

    @classmethod
    def set_cache_size(cls, maxlen):
        cls._ref_lru = deque(cls._weakref_lru, maxlen)

def map_sequence(fn, seq):
    if not isinstance(seq, Sequence):
        seq = list(seq)
    return LazySequence(seq, fn)

if __name__ == '__main__':
    import random

    def mk_slices(n):
        return [slice(random.randrange(0, 100),
                      random.randrange(-100, 0),
                      random.randrange(1, 10))
                for i in range(n)]

    def random_test(fn=None):
        seq = range(1000) if fn is None else map(fn, range(1000))
        seq = list(seq)
        lazy = LazySequence(list(range(1000)), fn)

        slices1 = mk_slices(10)
        slices2 = mk_slices(10)
        for s1, s2 in zip(slices1, slices2):
            lazy_s = lazy[s1]

            # Make sure LazySequences are copying state and
            # composing map functions correctly.
            wrc = lazy_s._base_seq
            lazy_s = LazySequence(lazy_s, lambda x: x * x)
            lazy_s = lazy_s[s2]
            assert wrc is lazy_s._base_seq

            # Make sure LazySequences slice like lists.
            seq_s = seq[s1]
            seq_s = list(map(lambda x: x * x, seq_s))
            seq_s = seq_s[s2]
            assert list(lazy_s) == seq_s, (
                'lazy_s and seq_s should be the same, but are not'
            )
            assert lazy_s == lazy_s

            # Make sure LazySequences are proper containers.
            if seq_s:
                n = seq_s[random.randrange(0, len(seq_s))]
                assert n in lazy_s, (
                    '{} should be in lazy_s but is not'.format(n)
                )
            else:
                assert not lazy_s, 'lazy_s should be empty but is not'

    print('Testing LazySequence with 1000 random inputs.')
    try:
        for i in range(1000):
            fn = None if random.randrange(0, 2) else lambda x: x * x
            random_test(fn)
    except AssertionError:
        print('Test failed.')
        raise
    else:
        print('Test passed.')
