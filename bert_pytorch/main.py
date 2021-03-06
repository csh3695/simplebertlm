import sys, os
import argparse
import time
import torch
import json
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import yaml
from dotmap import DotMap

from torch.optim import AdamW
from torch.utils.data import DataLoader

from bert_pytorch import model
from bert_pytorch.dataset import load_dataset, save_dataset
from bert_pytorch.trainer import linear_lr_scheduler
from bert_pytorch.model.utils import tester

with open('./bert_pytorch/template/base.yaml') as f:
    config = DotMap(yaml.load(f))
    config.eps = float(config.eps)

start_epoch = config.start

print(f'{config.start}~{config.epoch} | batch {config.batch_size} | mask_only {config.mask_only}')

#dataset = save_dataset(words_per_sent=512)
dataset = load_dataset()

bertlm = model.BERTLM(config)

if start_epoch != 0:
    try:
        bertlm.load_state_dict(torch.load(f'./bert_pytorch/model/model_saved/bert.ep{start_epoch-1}.mdl'))
    except:
        raise Exception("No File detected")

optimizer = AdamW(bertlm.parameters(), lr=1e-4)
criteria = nn.CrossEntropyLoss()


params = filter(lambda p: p.requires_grad, bertlm.parameters())
num_params = sum([np.prod(p.size()) for p in params])
print("# of params:", num_params)

cuda = True
loss_list = []
batch_size = config.batch_size
epoch = config.epoch
mask_only = True if config.mask_only=='True' else False

print(f"mask_only {mask_only}")

dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)
lr_sch = linear_lr_scheduler(start_val=1e-7, warm_step=len(dataloader)*2, warm_val=3e-5, end=len(dataloader) * 248,
                             i=1+(len(dataloader)*start_epoch))

#lr_list = [next(lr_sch) for _ in range(len(dataloader)*248)]

if cuda:
    bertlm = bertlm.cuda()

bertlm.train()

start = time.time()
ep_prev = start_epoch

for ep in range(start_epoch, epoch):
    for i, data in enumerate(dataloader):
        optimizer.zero_grad()
        x, mask, y, length = data
        if cuda:
            x = x.cuda()
            y = y.cuda()
        y_pred = bertlm(x)[0]

        source = torch.cat([y_pred[i][:length[i]] for i in range(len(length))], dim=0)
        target = torch.cat([y[i][:length[i]] for i in range(len(length))], dim=0)
        if mask_only:
            masked = torch.cat([mask[i][:length[i]] for i in range(len(length))], dim=0)
            loss = criteria(y_pred.reshape(-1, y_pred.shape[-1]), y.reshape(-1))
        else:
            loss = criteria(y_pred.reshape(-1, y_pred.shape[-1]), y.reshape(-1))
        loss_list.append(loss.item())
        loss.backward()
        optimizer.step()
        optimizer.param_groups[0]['lr'] = next(lr_sch)
        if i % 10 == 0:
            print(f"EP\t{ep} | data\t{i} | loss\t{loss:.8f} | lr\t{optimizer.param_groups[0]['lr']} "
                  f"| time\t{(time.time()-start):.3f}s")
            start = time.time()
        if i % 1000 == 0:
            tester.test_model(dataset, bertlm)
        #if i % 1000 == 0:
        #    sns.heatmap(y_pred[0].detach().cpu())
        #    plt.title(f"EP {ep} | data {i} | loss {loss:.8f} | lr {optimizer.param_groups[0]['lr']}")
        #    plt.show()
    torch.save(bertlm.state_dict(), f'./bert_pytorch/model/model_saved/bert.ep{ep}.mdl')

    if ep % 10 == 9:
        with open(f'./bert_pytorch/results/loss/loss_{ep_prev}_{ep}.json', 'w') as f:
            json.dump(loss_list, f)
        loss_list = []
        ep_prev = ep+1
