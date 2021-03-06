# -*- coding: utf-8 -*-
"""LanguageModel.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Z9Fn4bYa16NSDzxaTlRV_XRF4NDF1r2J

# 利用LSTM和GRU训练语言模型
"""

import os
import numpy as np
import torchtext
from torchtext.vocab import Vectors
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

# word vocab construction, idx->word, word->idx, <PAD>索引为0的部分
def word_set_construction(file_path):
  with open(file_path, 'r', encoding='utf-8') as f:
    text = f.readlines()
  words = [word for sent in text for word in sent.split()]
  words2idx = {w : i for i, w in enumerate(words, 1)} # 0 for PAD token
  idx2words = {i : w for i, w in enumerate(words, 1)}
  PAD_IDX = 0
  idx2words[PAD_IDX] = '<PAD>'
  words2idx['<PAD>'] = PAD_IDX
  return words, idx2words, words2idx

# read corpus: sentences
def read_corpus(file_path):
  with open(file_path, 'r', encoding='utf-8') as f:
    sents = f.readlines()
  sentences = [sent.strip() for sent in sents]
  return sentences

# data samples with labels
def samples_labels(corpus : list, words2idx, idx2words, max_len):
  samples = []
  labels = []
  for sample in tqdm(corpus):
    words = sample.split()
    sample_words = [0] * max_len
    for i, w in enumerate(words[:-1]):
      sample_words[i] = words2idx[w]

    target_words = [0] * max_len
    for i, w in enumerate(words[1:]):
      target_words[i] = words2idx[w]

    samples.append(sample_words)
    labels.append(target_words)

  return samples, labels

# get batches
def get_batches(samples, labels, batch_size):
  batch_data = []

  samples_tensor = torch.tensor(samples, dtype=torch.long)
  labels_tensor = torch.tensor(labels, dtype=torch.long)
  num, dim = samples_tensor.size()

  for start in range(0, num, batch_size):
    end = start + batch_size
    if end > num:
      break
    else:
      batch_samples = samples_tensor[start : end]
      batch_labels = samples_tensor[start : end]
    
    batch_data.append((batch_samples, batch_labels))

  return batch_data

## RNN-based language models
class LM_Models(nn.Module):
  def __init__(self, embedding_dim, hidden_dim, vocab_size, mode):
    super().__init__()
    self.hidden_dim = hidden_dim
    self.word_embedding = nn.Embedding(vocab_size, embedding_dim)
    if mode == 'LSTM' or 'lstm':
      self.model = nn.LSTM(embedding_dim, hidden_dim, batch_first=True)
    elif mode == 'GRU' or 'gru':
      self.model = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
    elif mode == 'RNN' or 'rnn':
      self.model = nn.RNN(embedding_dim, hidden_dim, batch_first=True)
    self.hidden2word = nn.Linear(hidden_dim, vocab_size)

  def forward(self, data):
    embeds = self.word_embedding(data)
    model_out, (h_n, c_n) = self.model(embeds)
    target_embed = self.hidden2word(model_out.contiguous().view(-1, self.hidden_dim))
    mask = (data != idx).view(-1)
    pure_target = target_embed[mask]
    target_scores = F.log_softmax(pure_target, dim=1)
    return target_scores

# evaluation 
def accuracy_score(y_hat, y):
  y_hat = y_hat.argmax(dim=1)
  num_pre_real = torch.eq(y_hat, y.view(-1))
  score = num_pre_real.sum().item() / num_pre_real.size()[0]
  return score

def evaluate(model, data):
  model.eval()
  total_acc = 0.
  total_count = 0.
  for x, y in data:
    mask = y != idx
    pure_y = y[mask]
    with torch.no_grad():
      target_scores = model(x)
    total_count += 1
    acc = accuracy_score(target_scores, pure_y)
    total_acc += acc
  
  acc = total_acc / total_count
  # model.train()
  return acc

# 定义文件所在路径
vocab_file = './bobsue.voc.txt'
train_file = './bobsue.lm.train.txt'
val_file = './bobsue.lm.dev.txt'
test_file = './bobsue.lm.dev.txt'

MAX_LEN = 20
BATCH_SIZE = 128
# get vocabs
words, idx2words, words2idx = word_set_construction(vocab_file)
# train batches data
train_corpus = read_corpus(train_file)
train_samples, train_labels = samples_labels(train_corpus, words2idx, idx2words, MAX_LEN)
train_batch_data = get_batches(train_samples, train_labels, BATCH_SIZE)
# val batches data
val_corpus = read_corpus(val_file)
val_samples, val_labels = samples_labels(val_corpus, words2idx, idx2words, MAX_LEN)
val_batch_data = get_batches(val_samples, val_labels, BATCH_SIZE)
# test batches data
test_corpus = read_corpus(test_file)
test_samples, test_labels = samples_labels(test_corpus, words2idx, idx2words, MAX_LEN)
test_batch_data = get_batches(test_samples, test_labels, BATCH_SIZE)

# function to train
EMBEDDING_DIM = 200
HIDDEN_DIM = 200
MODE = 'LSTM'
model = LM_Models(EMBEDDING_DIM, HIDDEN_DIM, len(words2idx), mode=MODE)
GRAD_CLIP = 5.
NUM_EPOCHS = 10
LR = 0.001

val_acces = []
loss_function = nn.NLLLoss()
optimizer = optim.Adam(model.parameters(), lr=LR)
scheduler = optim.lr_scheduler.ExponentialLR(optimizer, 0.5)

Model_Save_Name = 'LM-' + MODE + '-best.pth'
# print parameters
sum_ = 0
for name, param in model.named_parameters():
  mul = 1
  for size_ in param.shape:
    mul *= size_
  sum_ += mul
  print('%14s : %s' % (name, param.shape))
print('Total Num. of params：', sum_)

# train, val and test
for epoch in range(NUM_EPOCHS):
  model.train()
  print('epoch:{}'.format(epoch).center(51, '*'))
  idx = 0
  acc_list = []
  for i, (x, y) in enumerate(train_batch_data):  # x: train, y: label
    mask = y != idx
    pure_y = y[mask]
    # feedforward
    model.zero_grad()
    target_scores = model(x)
    acc = accuracy_score(target_scores, pure_y)
    acc_list.append(acc)
    # loss function
    loss = loss_function(target_scores, pure_y)
    # backpropagagtion
    loss.backward()
    # optim
    torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
    optimizer.step()
    if i % 20 == 0:
      print('epoch:{} item:{} loss:{:.4} acc:{:.4}'.format(epoch, i, loss.item(), acc))

  print('Epoch:{} avg acc:{:.4}'.format(epoch, sum(acc_list)/len(acc_list)))

  # eval
  val_acc = evaluate(model, val_batch_data)
  if len(val_acces) == 0 or val_acc > max(val_acces):
    print('Best model, val Accuracy: {:.4}'.format(val_acc))
    torch.save(model.state_dict(), Model_Save_Name)
  else:
    print('Current val Accuracy: {:.4}'.format(val_acc))
    scheduler.step()
  val_acces.append(val_acc)

  # test
  test_acc = evaluate(model, test_batch_data)
  print('Test data accuracy: {:.4}'.format(test_acc))

# print incorrect prediction
def print_incorrect_prediction(model, data):
  model.eval()
  incorrect_words = []
  for x, y in data:
    mask = [y != 0]
    y = y[mask]
    with torch.no_grad():
      target_scores = model(x)
    y_hat = target_scores.argmax(dim=1)

    for i, j in zip(y_hat.tolist(), y.tolist()):
      if i != j:
        incorrect_words.append('|'.join([idx2words[i], idx2words[j]]))
  return incorrect_words

model.load_state_dict(torch.load(Model_Save_Name))
incorrect_predictions = print_incorrect_prediction(model, test_batch_data)
for inc_pred in incorrect_predictions:
  print(inc_pred)

