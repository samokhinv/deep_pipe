"""
Contains a few more sophisticated commands
that are usually accessed via the `do.py` script.
"""

import os
from collections import defaultdict
from typing import Callable, Iterable

import numpy as np
from tqdm import tqdm

from dpipe.io import dump_json


def np_filename2id(filename):
    *rest, extension = filename.split('.')
    assert extension == 'npy', f'Expected npy file, got {extension} from {filename}'
    return '.'.join(rest)


@np.deprecate
def train_model(train, model, save_model_path, restore_model_path=None, modify_state_fn=None):
    if restore_model_path is not None:
        model.load(restore_model_path, modify_state_fn=modify_state_fn)

    train()
    model.save(save_model_path)


def transform(input_path, output_path, transform_fn):
    os.makedirs(output_path)

    for f in tqdm(os.listdir(input_path)):
        np.save(os.path.join(output_path, f), transform_fn(np.load(os.path.join(input_path, f))))


def map_ids_to_disk(func: Callable[[str], object], ids: Iterable[str], output_path: str, exist_ok: bool = False):
    """
    Apply `func` to each id from `ids` and save each output to `output_path`.
    If `exists_ok` is True the existing files will be ignored, otherwise an exception is raised.
    """
    os.makedirs(output_path, exist_ok=exist_ok)

    for identifier in ids:
        output = os.path.join(output_path, f'{identifier}.npy')
        if exist_ok and os.path.exists(output):
            continue

        value = func(identifier)

        # To save disk space
        if isinstance(value, np.ndarray) and np.issubdtype(value.dtype, np.floating):
            value = value.astype(np.float16)

        np.save(output, value)
        # saving some memory
        del value


def predict(ids, output_path, load_x, predict_fn, exist_ok=False):
    map_ids_to_disk(lambda identifier: predict_fn(load_x(identifier)), tqdm(ids), output_path, exist_ok)


def evaluate_aggregated_metrics(load_y_true, metrics: dict, predictions_path, results_path, exist_ok=False):
    assert len(metrics) > 0, 'No metric provided'
    os.makedirs(results_path, exist_ok=exist_ok)

    targets, predictions = [], []
    for filename in tqdm(sorted(os.listdir(predictions_path))):
        predictions.append(np.load(os.path.join(predictions_path, filename)))
        targets.append(load_y_true(np_filename2id(filename)))

    for name, metric in metrics.items():
        score = metric(targets, predictions)
        if isinstance(score, np.ndarray):
            score = score.tolist()

        dump_json(score, os.path.join(results_path, name + '.json'), indent=0)


def evaluate_individual_metrics(load_y_true, metrics: dict, predictions_path, results_path, exist_ok=False):
    assert len(metrics) > 0, 'No metric provided'
    os.makedirs(results_path, exist_ok=exist_ok)

    results = defaultdict(dict)

    for filename in tqdm(sorted(os.listdir(predictions_path))):
        identifier = np_filename2id(filename)
        y_prob = np.load(os.path.join(predictions_path, filename))
        y_true = load_y_true(identifier)

        for metric_name, metric in metrics.items():
            score = metric(y_true, y_prob)
            if isinstance(score, np.ndarray):
                score = score.tolist()
            results[metric_name][identifier] = score

    for metric_name, result in results.items():
        dump_json(result, os.path.join(results_path, metric_name + '.json'), indent=0)
