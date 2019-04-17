import numpy as np

from dpipe.medim.axes import broadcast_to_axes, AxesLike, AxesParams
from dpipe.medim.grid import divide, combine
from dpipe.medim.itertools import extract
from dpipe.medim.shape_ops import pad_to_shape, crop_to_shape
from dpipe.medim.utils import extract_dims
from dpipe.predict.utils import add_dims


def add_extract_dims(n_add: int = 1, n_extract: int = None):
    if n_extract is None:
        n_extract = n_add

    def decorator(predict):
        def wrapper(x):
            x = add_dims(x, ndims=n_add)[0]
            x = predict(x)
            return extract_dims(x, n_extract)

        return wrapper

    return decorator


def patches_grid(patch_size: AxesLike, stride: AxesLike, axes: AxesLike = None, padding_values: AxesParams = 0,
                 ratio: AxesParams = 0.5):
    """
    Divide an incoming array into patches of corresponding ``patch_size`` and ``stride`` and then combine them
    by averaging the overlapping regions.

    If ``padding_values`` is not None, the array will be padded to an appropriate shape to make a valid division.
    Afterwards the padding is removed.

    See Also
    --------
    `grid.divide` `grid.combine` `pad_to_shape`
    """
    axes, path_size, stride = broadcast_to_axes(axes, patch_size, stride)
    valid = padding_values is not None

    def decorator(predict):
        def wrapper(x):
            if valid:
                shape = np.array(x.shape)[list(axes)]
                new_shape = shape + (stride - shape + patch_size) % stride
                x = pad_to_shape(x, new_shape, axes, padding_values, ratio)

            patches = map(predict, divide(x, patch_size, stride, axes))
            prediction = combine(patches, extract(x.shape, axes), stride, axes)

            if valid:
                prediction = crop_to_shape(prediction, shape, axes, ratio)
            return prediction

        return wrapper

    return decorator