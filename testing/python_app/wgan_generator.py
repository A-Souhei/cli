# wgan_generator.py

import tensorflow as tf
from tensorflow.keras.models import Model, Sequential
from tensorflow.keras.layers import Dense, LeakyReLU, BatchNormalization, Dropout
from tensorflow.keras.optimizers import Adam

def build_generator(latent_dim):
    model = Sequential()
    model.add(Dense(256, input_dim=latent_dim))
    model.add(BatchNormalization())
    model.add(LeakyReLU(alpha=0.2))
    
    model.add(Dense(512))
    model.add(BatchNormalization())
    model.add(LeakyReLU(alpha=0.2))
    
    model.add(Dense(1024))
    model.add(BatchNormalization())
    model.add(LeakyReLU(alpha=0.2))
    
    model.add(Dense(784, activation='tanh'))
    return model

def build_discriminator(input_shape):
    model = Sequential()
    model.add(Dense(1024, input_dim=input_shape[0]))
    model.add(LeakyReLU(alpha=0.2))
    model.add(Dropout(0.3))
    
    model.add(Dense(512))
    model.add(LeakyReLU(alpha=0.2))
    model.add(Dropout(0.3))
    
    model.add(Dense(256))
    model.add(LeakyReLU(alpha=0.2))
    model.add(Dropout(0.3))
    
    # WGAN critic outputs unbounded real values (no sigmoid activation)
    model.add(Dense(1))
    return model

def wgan_generator_loss(y_true, y_pred):
    """WGAN generator loss: maximize discriminator output for fake samples."""
    return -tf.reduce_mean(y_pred)

def wgan_discriminator_loss(real_output, fake_output):
    """WGAN discriminator (critic) loss: maximize difference between real and fake."""
    return tf.reduce_mean(fake_output) - tf.reduce_mean(real_output)

latent_dim = 100
input_shape = (784,)  # Example input shape for MNIST data

generator = build_generator(latent_dim)
discriminator = build_discriminator(input_shape)

# Combine networks into a WGAN model
optimizer_g = Adam(learning_rate=0.0002, beta_1=0.5)
optimizer_d = Adam(learning_rate=0.0002, beta_1=0.5)

generator.compile(loss=wgan_generator_loss, optimizer=optimizer_g)
discriminator.trainable = False
combined_model = Model(generator.input, discriminator(generator.output))
combined_model.compile(loss=wgan_generator_loss, optimizer=optimizer_d)

# Example usage:
# noise = np.random.normal(0, 1, (batch_size, latent_dim))
# generated_data = generator.predict(noise)
# real_data = np.array(real_samples)
# d_loss_real = discriminator.train_on_batch(real_data, np.ones((batch_size, 1)))
# d_loss_fake = discriminator.train_on_batch(generated_data, np.zeros((batch_size, 1)))