from typing import Union, Callable

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.colors import Colormap

from .hsv import gray_image_colored_mask, gray_image_bright_colored_mask, segmentation_probabilities
from .checks import check_shape_along_axis
from .utils import makedirs_top
from .axes import AxesParams


def _get_rows_cols(max_cols, data):
    columns = min(len(data), max_cols or len(data))
    return (len(data) - 1) // columns + 1, columns


def _slice_base(data: [np.ndarray], axis: int = -1, scale: int = 5, max_columns: int = None, colorbar: bool = False,
                show_axes: bool = False, cmap: Union[Colormap, str] = 'gray', vlim: AxesParams = None,
                callback: Callable = None, sliders: dict = None):
    from ipywidgets import interact, IntSlider
    check_shape_along_axis(*data, axis=axis)
    vlim = np.broadcast_to(vlim, [len(data), 2]).tolist()
    rows, columns = _get_rows_cols(max_columns, data)
    sliders = sliders or {}
    if 'idx' in sliders:
        raise ValueError(f'Overriding "idx" is not allowed.')

    def update(idx, **kwargs):
        fig, axes = plt.subplots(rows, columns, figsize=(scale * columns, scale * rows))
        for ax, x, (vmin, vmax) in zip(np.array(axes).flatten(), data, vlim):
            im = ax.imshow(x.take(idx, axis=axis), cmap=cmap, vmin=vmin, vmax=vmax)
            if colorbar:
                fig.colorbar(im, ax=ax, orientation='horizontal')
            if not show_axes:
                ax.set_axis_off()

        if callback is not None:
            callback(axes, idx=idx, **kwargs)

        plt.tight_layout()
        plt.show()

    interact(update, idx=IntSlider(min=0, max=data[0].shape[axis] - 1, continuous_update=False), **sliders)


def slice3d(*data: np.ndarray, axis: int = -1, scale: int = 5, max_columns: int = None, colorbar: bool = False,
            show_axes: bool = False, cmap: Union[Colormap, str] = 'gray', vlim: AxesParams = None):
    """
    Creates an interactive plot, simultaneously showing slices along a given ``axis`` for all the passed images.

    Parameters
    ----------
    data
    axis
    scale
        the figure scale.
    max_columns
        the maximal number of figures in a row. If None - all figures will be in the same row.
    colorbar
        Whether to display a colorbar.
    show_axes
        Whether to do display grid on the image.
    cmap
    vlim
        used to normalize luminance data. If None - the limits are determined automatically.
        Must be broadcastable to (len(data), 2). See `matplotlib.pyplot.imshow` (vmin and vmax) for details.
    """
    _slice_base(data, axis, scale, max_columns, colorbar, show_axes, cmap, vlim)


def animate3d(*data: np.ndarray, output_path: str, axis: int = -1, scale: int = 5, max_columns: int = None,
              colorbar: bool = False, show_axes: bool = False, cmap: str = 'gray', vlim=(None, None), fps: int = 30,
              writer: str = 'imagemagick', repeat: bool = True):
    """
    Saves an animation to ``output_path``, simultaneously showing slices
    along a given ``axis`` for all the passed images.

    Parameters
    ----------
    data: np.ndarray
    output_path: str
    axis: int
    scale: int
        the figure scale.
    max_columns: int
        the maximal number of figures in a row. If None - all figures will be in the same row.
    colorbar: bool
        Whether to display a colorbar. Works only if ``vlim``s are not None.
    show_axes: bool
        Whether to do display grid on the image.
    cmap,vlim:
        parameters passed to matplotlib.pyplot.imshow
    fps: int
    writer: str
    repeat: bool
        whether the animation should repeat when the sequence of frames is completed.
    """
    check_shape_along_axis(*data, axis=axis)
    rows, columns = _get_rows_cols(max_columns, data)
    fig, axes = plt.subplots(rows, columns, figsize=(scale * columns, scale * rows))

    images = []
    has_vlim = all(x is not None for x in vlim)
    for ax, x in zip(np.array(axes).flatten(), data):
        image = ax.imshow(x.take(0, axis=axis), cmap=cmap, vmin=vlim[0], vmax=vlim[1], animated=True)
        if colorbar and has_vlim:
            fig.colorbar(image, ax=ax, orientation='horizontal')
        if not show_axes:
            ax.set_axis_off()
        images.append(image)

    def update(idx):
        for img, entry in zip(images, data):
            img.set_data(entry.take(idx, axis=axis))
            if not has_vlim:
                img.autoscale()

        return images

    plt.tight_layout()
    makedirs_top(output_path, exist_ok=True)
    FuncAnimation(fig, func=update, frames=data[0].shape[axis], blit=True, repeat=repeat).save(
        output_path, writer=writer, fps=fps)
