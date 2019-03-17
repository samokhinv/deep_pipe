from itertools import islice
from typing import Iterable, Callable, Union

import pdp
import numpy as np

from ..medim.axes import AxesParams
from .base import BatchIter
from .utils import pad_batch_equal

__all__ = 'combine_batches', 'combine_to_arrays', 'combine_pad', 'make_infinite_batch_iter'


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


def combine_pad(inputs, padding_values: AxesParams = 0, ratio: AxesParams = 0):
    """
    Combines tuples from ``inputs`` into batches and pads each batch in order to obtain
    a correctly shaped numpy array.

    See Also
    --------
    `pad_to_shape`
    """
    return tuple(pad_batch_equal(x, padding_values, ratio) for x in combine_batches(inputs))


def make_infinite_batch_iter(
        source: Union[Iterable, pdp.Source], *transformers: Union[Callable, pdp.One2One, pdp.One2Many],
        batch_size: int, n_iters_per_epoch: int, buffer_size: int = 3, combiner: Callable = combine_to_arrays):
    """
    Combine ``source`` and ``transformers`` into a batch iterator that yields batches of size ``batch_size``.

    Parameters
    ----------
    source
        an infinite iterable.
    transformers
        a callable that transforms the objects generated by the previous element of the pipeline.
    batch_size
    n_iters_per_epoch
        how many batches to yield before exhaustion.
    buffer_size
        how many objects to keep buffered in each pipeline element.
    combiner
        combines chunks of single batches in multiple batches, e.g. combiner([(x, y), (x, y)]) -> ([x, x], [y, y])
    """
    if n_iters_per_epoch <= 0:
        raise ValueError(f'Expected a positive amount of iterations per epoch, but got {n_iters_per_epoch}')

    # backwards compatibility with pdp==0.2.1
    if hasattr(pdp.interface, 'ComponentDescription'):
        source_class = transformer_class = pdp.interface.ComponentDescription
    else:
        source_class = pdp.Source
        transformer_class = pdp.interface.TransformerDescription

    def wrap(o):
        if not isinstance(o, transformer_class):
            o = pdp.One2One(o, buffer_size=buffer_size)
        return o

    if not isinstance(source, source_class):
        source = pdp.Source(source, buffer_size=buffer_size)

    pipeline = pdp.Pipeline(source, *map(wrap, transformers), pdp.Many2One(chunk_size=batch_size, buffer_size=3),
                            pdp.One2One(combiner, buffer_size=buffer_size))

    class Pipeline(BatchIter):
        """Wrapper for `pdp.Pipeline`."""

        def close(self):
            self.__exit__(None, None, None)

        def __iter__(self):
            if not pipeline.pipeline_active:
                self.__enter__()
            return islice(pipeline, n_iters_per_epoch)

        def __enter__(self):
            pipeline.__enter__()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return pipeline.__exit__(exc_type, exc_val, exc_tb)

        def __del__(self):
            self.close()

    return Pipeline()
