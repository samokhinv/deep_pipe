Training
========

``deep_pipe`` has a unified interface for training models. We will show
an example for a model written in PyTorch.

.. code-block:: python3

    from dpipe.train import train

this is the main function; it requires a batch iterator, and a
``train_step`` function, that performs a forward-backward pass for a
given batch.

Let's build all the required components.

Batch iterator
~~~~~~~~~~~~~~

The batch iterators are covered in a separate tutorial
(:doc:`batch\_iter`), we'll reuse the code from it:

.. code-block:: python3

    from torchvision.datasets import MNIST
    from dpipe.batch_iter import Infinite, sample, apply_at
    from pathlib import Path
    import numpy as np
    
    # download to ~/tests/MNIST, if necessary
    dataset = MNIST(Path('~/tests/MNIST').expanduser(), transform=np.array, download=True)
    
    
    # yield 10 batches of size 30 each epoch:
    
    batch_iter = Infinite(
        sample(dataset),
        apply_at(0, lambda x: x[None].astype('float32')), # add channels dim
        batch_size=30, batches_per_epoch=10,
    )

Train Step
~~~~~~~~~~

Next, we will implement the function that performs a train\_step. But
first we need an architecture:

.. code-block:: python3

    import torch
    from torch import nn
    from dpipe import layers
    
    
    architecture = nn.Sequential(
        nn.Conv2d(1, 32, kernel_size=3),
        nn.ReLU(),
        nn.Conv2d(32, 64, kernel_size=3),
        nn.ReLU(),
        nn.Conv2d(64, 128, kernel_size=3),
        
        nn.AdaptiveMaxPool2d((1, 1)),
        nn.Flatten(),
        
        nn.ReLU(),
        nn.Linear(128, 10),
    )
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(architecture.parameters(), lr=1e-3)

.. code-block:: python3

    from dpipe.torch import to_var, to_np
    
    def cls_train_step(images, labels):
        # move images and labels to same device as architecture
        images, labels = to_var(images, labels, device=architecture)
        architecture.train()
        
        logits = architecture(images)
        loss = criterion(logits, labels)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        # `train_step` must return the loss which will be later user for logging
        return to_np(loss)

Training the model
~~~~~~~~~~~~~~~~~~

Next, we just run the ``train`` function:

.. code-block:: python3

    train(cls_train_step, batch_iter, n_epochs=10)

A more general version of the function ``cls_train_step`` is already
available in dpipe:

.. code-block:: python3

    from dpipe.torch import train_step

Apart from the input batches it requires the following arguments:
``architecture``, ``optimizer``, ``criterion``. We can pass these
arguments directly to ``train``, so the previous call is equivalent to:

.. code-block:: python3

    train(
        train_step, batch_iter, n_epochs=10, 
        architecture=architecture, optimizer=optimizer, criterion=criterion
    )

Logging
~~~~~~~

After calling ``train`` the interpreter just “hangs” until the training
is over. In order to log various information about the training process,
you can pass a logger:

.. code-block:: python3

    from dpipe.train import ConsoleLogger
    
    train(
        train_step, batch_iter, n_epochs=3, logger=ConsoleLogger(),
        architecture=architecture, optimizer=optimizer, criterion=criterion
    )


.. parsed-literal::

    00000: train loss: 0.29427966475486755
    00001: train loss: 0.26119616627693176
    00002: train loss: 0.2186189591884613


There are various logger implementations, e.g. one that writes in a
format, readable by tensorboard - `TBLogger`.

Checkpoints
~~~~~~~~~~~

It is often useful to keep checkpoints (or snapshots) of you model and
optimizer in case you may want to resotore them. To do that, pass the
``checkpoints`` argument:

.. code-block:: python3

    from dpipe.train import Checkpoints
    
    
    checkpoints = Checkpoints(
        'PATH/TO/CHECKPOINTS/FOLDER', 
        [architecture, optimizer],
    )
    
    train(
        train_step, batch_iter, n_epochs=3, checkpoints=checkpoints,
        architecture=architecture, optimizer=optimizer, criterion=criterion
    )

The cool part is that if the training is prematurely stopped, e.g. by an
exception, you can resume the training from the same point instead of
starting over:

.. code-block:: python3

    train(
        train_step, batch_iter, n_epochs=3, checkpoints=checkpoints,
        architecture=architecture, optimizer=optimizer, criterion=criterion
    )
    # ... something bad happened, e.g. KeyboardInterrupt
    
    # start from where you left off
    train(
        train_step, batch_iter, n_epochs=3, checkpoints=checkpoints,
        architecture=architecture, optimizer=optimizer, criterion=criterion
    )

Value Policies
~~~~~~~~~~~~~~

You can further customize the training process by passing addtitional
values to ``train_step`` that change in time.

For example, ``train_step`` takes an optional argument ``lr`` - used to
update the ``optimizer``'s learning rate.

We can change this value after each trainig epoch using the
`ValuePolicy` interface. Let's use an exponential learning rate:

.. code-block:: python3

    from dpipe.train import Exponential
    
    train(
        train_step, batch_iter, n_epochs=10, 
        architecture=architecture, optimizer=optimizer, criterion=criterion,
        lr=Exponential(initial=1e-3, multiplier=0.5, step_length=3) # decrease by a factor of 2 every 3 epochs
    )

Validation
~~~~~~~~~~

Finally, you may want to evaluate your network on a separate validation
set after each epoch. This is done by the ``validate`` argument. It
expects a function that simply returns a dictionary with the calculated
metrics, e.g.:

.. code-block:: python3

    def validate():
        architecture.eval()
        
        # ... predict on validation set
        pred = ...
        ys = ...
        
        acc = accuracy_score(ys, pred)
        return {
            'acuracy': acc
        }
    
    train(
        train_step, batch_iter, n_epochs=10, validate=validate,
        architecture=architecture, optimizer=optimizer, criterion=criterion,
    )
