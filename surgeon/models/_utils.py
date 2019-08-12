import numpy as np
import tensorflow as tf
from keras import backend as K


def compute_kernel(x, y, kernel='rbf', **kwargs):
    """
        Computes RBF kernel between x and y.
        # Parameters
            x: Tensor
                Tensor with shape [batch_size, z_dim]
            y: Tensor
                Tensor with shape [batch_size, z_dim]
        # Returns
            returns the computed RBF kernel between x and y
    """
    scales = kwargs.get("scales", [])
    if kernel == "rbf":
        x_size = K.shape(x)[0]
        y_size = K.shape(y)[0]
        dim = K.shape(x)[1]
        tiled_x = K.tile(K.reshape(x, K.stack([x_size, 1, dim])), K.stack([1, y_size, 1]))
        tiled_y = K.tile(K.reshape(y, K.stack([1, y_size, dim])), K.stack([x_size, 1, 1]))
        return K.exp(-K.mean(K.square(tiled_x - tiled_y), axis=2) / K.cast(dim, tf.float32))
    elif kernel == 'raphy':
        scales = K.variable(value=np.asarray(scales))
        squared_dist = K.expand_dims(squared_distance(x, y), 0)
        scales = K.expand_dims(K.expand_dims(scales, -1), -1)
        weights = K.eval(K.shape(scales)[0])
        weights = K.variable(value=np.asarray(weights))
        weights = K.expand_dims(K.expand_dims(weights, -1), -1)
        return K.sum(weights * K.exp(-squared_dist / (K.pow(scales, 2))), 0)
    elif kernel == "multi-scale-rbf":
        sigmas = [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 5, 10, 15, 20, 25, 30, 35, 100, 1e3, 1e4, 1e5, 1e6]

        beta = 1. / (2. * (K.expand_dims(sigmas, 1)))
        distances = squared_distance(x, y)
        s = K.dot(beta, K.reshape(distances, (1, -1)))

        return K.reshape(tf.reduce_sum(tf.exp(-s), 0), K.shape(distances)) / len(sigmas)


def squared_distance(x, y):  # returns the pairwise euclidean distance
    r = K.expand_dims(x, axis=1)
    return K.sum(K.square(r - y), axis=-1)


def compute_mmd(x, y, kernel, **kwargs):  # [batch_size, z_dim] [batch_size, z_dim]
    """
        Computes Maximum Mean Discrepancy(MMD) between x and y.
        # Parameters
            x: Tensor
                Tensor with shape [batch_size, z_dim]
            y: Tensor
                Tensor with shape [batch_size, z_dim]
        # Returns
            returns the computed MMD between x and y
    """
    x_kernel = compute_kernel(x, x, kernel=kernel, **kwargs)
    y_kernel = compute_kernel(y, y, kernel=kernel, **kwargs)
    xy_kernel = compute_kernel(x, y, kernel=kernel, **kwargs)
    return K.mean(x_kernel) + K.mean(y_kernel) - 2 * K.mean(xy_kernel)


def sample_z(args):
    """
        Samples from standard Normal distribution with shape [size, z_dim] and
        applies re-parametrization trick. It is actually sampling from latent
        space distributions with N(mu, var) computed in `_encoder` function.
        # Parameters
            No parameters are needed.
        # Returns
            The computed Tensor of samples with shape [size, z_dim].
    """
    mu, log_var = args
    batch_size = K.shape(mu)[0]
    z_dim = K.int_shape(mu)[1]
    eps = K.random_normal(shape=[batch_size, z_dim])
    return mu + K.exp(log_var / 2) * eps
