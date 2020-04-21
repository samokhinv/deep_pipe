from itertools import islice
from typing import Iterable, Callable

import numpy as np

from ..im.axes import AxesParams
from .utils import pad_batch_equal

__all__ = 'Infinite', 'combine_batches', 'combine_to_arrays', 'combine_pad'


def combine_batches(inputs):
    """
    Combines tuples from ``inputs`` into batches: [(x, y), (x, y)] -> [(x, x), (y, y)]
    """
    return tuple(zip(*inputs))


def combine_to_arrays(inputs):
    """
    Combines tuples from ``inputs`` into batches of numpy arrays.
    """
    return tuple(map(np.array, combine_batches(inputs)))


def combine_pad(inputs, padding_values: AxesParams = 0, ratio: AxesParams = 0.5):
    """
    Combines tuples from ``inputs`` into batches and pads each batch in order to obtain
    a correctly shaped numpy array.

    References
    ----------
    `pad_to_shape`
    """
    return tuple(pad_batch_equal(x, padding_values, ratio) for x in combine_batches(inputs))


class Infinite:
    """
    Combine ``source`` and ``transformers`` into a batch iterator that yields batches of size ``batch_size``.

    Parameters
    ----------
    source: Iterable
        an infinite iterable.
    transformers: Callable
        the callable that transforms the objects generated by the previous element of the pipeline.
    batch_size: int
        the size of batch.
    batches_per_epoch: int, None, optional
        the number of batches to yield each epoch.
    buffer_size: int
        the number of objects to keep buffered in each pipeline element. Default is 3.
    combiner: Callable
        combines chunks of single batches in multiple batches, e.g. combiner([(x, y), (x, y)]) -> ([x, x], [y, y]).
        Default is `combine_to_arrays`.

    References
    ----------
    See the :doc:`tutorials/batch_iter` tutorial for more details.
    """

    def __init__(self, source: Iterable, *transformers: Callable, batch_size: int, batches_per_epoch: int,
                 buffer_size: int = 3, combiner: Callable = combine_to_arrays):
        import pdp
        from pdp.interface import ComponentDescription

        if batches_per_epoch <= 0:
            raise ValueError(f'Expected a positive amount of batches per epoch, but got {batches_per_epoch}')

        def wrap(o):
            if not isinstance(o, ComponentDescription):
                o = pdp.One2One(o, buffer_size=buffer_size)
            return o

        if not isinstance(source, ComponentDescription):
            source = pdp.Source(source, buffer_size=buffer_size)

        self.batches_per_epoch = batches_per_epoch
        self.pipeline = pdp.Pipeline(
            source, *map(wrap, transformers), pdp.Many2One(chunk_size=batch_size, buffer_size=1),
            pdp.One2One(combiner, buffer_size=buffer_size))

    def close(self):
        """Stop all background processes."""
        self.__exit__(None, None, None)

    def __call__(self):
        if not self.pipeline.pipeline_active:
            self.__enter__()
        return islice(self.pipeline, self.batches_per_epoch)

    def __enter__(self):
        self.pipeline.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.pipeline.__exit__(exc_type, exc_val, exc_tb)

    def __del__(self):
        self.close()
