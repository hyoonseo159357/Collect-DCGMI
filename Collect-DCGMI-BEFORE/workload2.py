from datetime import datetime
import math
import time
import pickle
import argparse
import tensorflow as tf
import numpy as np
import dataset_info
import model_info
import os

# GPU device check
device_name = tf.test.gpu_device_name()
if not device_name:
    print('Cannot found GPU. Training with CPU')
else:
    print('Found GPU at :{}'.format(device_name))

# Get arguments for job
parser = argparse.ArgumentParser()
parser.add_argument('--dataset', default=224, type=int)
parser.add_argument('--model', default='VGG19', type=str)
parser.add_argument('--batch_size', default=128, type=int)
parser.add_argument('--prof_point', default=10, type=float)
parser.add_argument('--optimizer', default='SGD', type=str)
parser.add_argument('--instance_type', default='EC2', type=str)
args = parser.parse_args()
    
# Dataset Info
dataset = dataset_info.select_dataset(args.dataset)
model_name = args.model

num_classes = dataset['num_classes']
img_rows = dataset['img_rows']
img_cols = dataset['img_cols']
img_channels = dataset['img_channels']
num_data = dataset['num_data']
num_test = dataset['num_test']

batch_size = args.batch_size
prof_point = args.prof_point
batch_num = math.ceil(num_data/batch_size)
epochs = math.ceil(prof_point)
optimizer = 'SGD'
file_name_dcgm = str(model_name)+'_batchsize'+str(batch_size)+'_datasize'+str(args.dataset)+'_total_epoch'+str(epochs)+"_totaldata"+str(num_data) + ".txt"
file_name_dstat = 'dstat_'+str(model_name)+'_batchsize'+str(batch_size)+'_datasize'+str(args.dataset)+'_total_epoch'+str(epochs)+"_totaldata"+str(num_data) + ".csv"
file_name_epoch_batch_latency = 'latency_'+str(model_name)+'_batchsize'+str(batch_size)+'_datasize'+str(args.dataset)+'_total_epoch'+str(epochs)+"_totaldata"+str(num_data)
latency_filename= './'+str(model_name)+'_batchsize'+str(batch_size)+'_datasize'+str(args.dataset)+'_total_epoch'+str(epochs)+"_totaldata"+str(num_data)+'.csv'           

###################### Build Fake Dataset ######################
x_train_shape = (num_data, img_rows, img_cols, img_channels)
y_train_shape = (num_data, 1)

x_test_shape = (num_test, img_rows, img_cols, img_channels)
y_test_shape = (num_test, 1)

x_train = np.random.rand(*x_train_shape)
y_train = np.random.randint(num_classes, size=y_train_shape)
x_test = np.random.rand(*x_test_shape)
y_test = np.random.randint(num_classes, size=y_test_shape)
###############################################################
if tf.keras.backend.image_data_format() == 'channels_first':
    x_train = x_train.reshape(x_train.shape[0], img_channels, img_rows, img_cols)
    x_test = x_test.reshape(x_test.shape[0], img_channels, img_rows, img_cols)
    input_shape = (img_channels, img_rows, img_cols)
else:
    x_train = x_train.reshape(x_train.shape[0], img_rows, img_cols, img_channels)
    x_test = x_test.reshape(x_test.shape[0], img_rows, img_cols, img_channels)
    input_shape = (img_rows, img_cols, img_channels)
    
x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
y_train = tf.keras.utils.to_categorical(y_train, num_classes)
y_test = tf.keras.utils.to_categorical(y_test, num_classes)

# Select model from model info module
model = model_info.select_model(model_name, input_shape, num_classes)
model.compile(loss=tf.keras.losses.categorical_crossentropy,
              optimizer=optimizer,
              metrics=['accuracy'])


epoch_dict = {}
class TrainCallback(tf.keras.callbacks.Callback):
    def on_train_begin(self, logs=None):
        os.system("./dcgmi_field.sh &")
        os.system("./dstat.sh &")
        self.all_times = []
        
    def on_train_end(self, logs=None):
        os.system("mv dcgmi-log.txt " + file_name_dcgm )
        os.system("sudo pkill -9 -f dcgmi")
        os.system("mv dstat-log.csv " + file_name_dstat )
        os.system("sudo pkill -9 -f dstat")
        
        time_filename = f'./{file_name_epoch_batch_latency}.pickle'
        time_file = open(time_filename, 'ab')
        pickle.dump(self.all_times, time_file)
        time_file.close()
        
    def on_epoch_begin(self, epoch, logs=None):
        self.epoch_times = []
        self.epoch_time_start = time.time()
        
    def on_epoch_end(self, epoch, logs=None):
        self.epoch_time_end = time.time()
        self.all_times.append(self.epoch_time_end - self.epoch_time_start)
        self.all_times.append(self.epoch_times)
        
    def on_train_batch_begin(self, batch, logs=None):
        self.batch_time_start = time.time()
        
    def on_train_batch_end(self, batch, logs=None):
        self.epoch_times.append(time.time() - self.batch_time_start)

        
model.fit(x_train, y_train,
    batch_size=batch_size,
    epochs=epochs,
    verbose=1,
    validation_data=(x_test, y_test),
    callbacks = TrainCallback())


# save data
with open(latency_filename,'wb') as fw:
    pickle.dump(epoch_dict, fw)
# load data
with open(latency_filename, 'rb') as fr:
    user_loaded = pickle.load(fr)
# show data
print(user_loaded)
