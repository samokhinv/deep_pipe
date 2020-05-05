from itertools import islice
from typing import Iterable, Callable, Union

import numpy as np

from ..itertools import zip_equal
from ..im.axes import AxesParams
from .utils import pad_batch_equal

__all__ = 'Infinite', 'combine_batches', 'combine_to_arrays', 'combine_pad'


def combine_batches(inputs):
    """
    Combines tuples from ``inputs`` into batches: [(x, y), (x, y)] -> [(x, x), (y, y)]
    """
    return tuple(zip_equal(*inputs))


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
    batches = combine_batches(inputs)
    padding_values = np.broadcast_to(padding_values, [len(batches)])
    return tuple(pad_batch_equal(x, values, ratio) for x, values in zip(batches, padding_values))


class Infinite:
    """
    Combine ``source`` and ``transformers`` into a batch iterator that yields batches of size ``batch_size``.

    Parameters
    ----------
    source: Iterable
        an infinite iterable.
    transformers: Callable
        the callable that transforms the objects generated by the previous element of the pipeline.
    batch_size: int, Callable
        the size of batch.
    batches_per_epoch: int
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

    def __init__(self, source: Iterable, *transformers: Callable,
                 batch_size: Union[int, Callable], batches_per_epoch: int,
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
            source, *map(wrap, transformers),
            self._make_combiner(batch_size),
            pdp.One2One(combiner, buffer_size=buffer_size)
        )

    @staticmethod
    def _make_combiner(batch_size):
        from pdp.interface import ComponentDescription
        from pdp.base import start_transformer

        if callable(batch_size):
            should_add = batch_size

        elif isinstance(batch_size, int):
            if batch_size <= 0:
                raise ValueError(f'`batch_size` must be greater than zero, not {batch_size}.')

            def should_add(chunk, item):
                return len(chunk) < batch_size

        else:
            raise TypeError(f'`batch_size` must be either int or callable, not {type(batch_size)}.')

        def start_combiner(q_in, q_out, stop_event):
            chunk = []

            def process_data(item):
                nonlocal chunk
                if not chunk or should_add(chunk, item):
                    chunk.append(item)
                else:
                    q_out.put(chunk)
                    chunk = [item]

            start_transformer(process_data, q_in, q_out, stop_event=stop_event, n_workers=1)

        return ComponentDescription(start_combiner, 1, 1)

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
