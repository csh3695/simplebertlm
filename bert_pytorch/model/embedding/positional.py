import math
import torch
import torch.nn as nn
from bert_pytorch.model.utils import GELU


class SinusoidalPositionalEmbedding(nn.Module):
    def __init__(self, dim, max_len=512):
        super().__init__()

        # Compute the positional encodings once in log space.
        pe = torch.zeros(max_len, dim).float()
        pe.require_grad = False

        position = torch.arange(0, max_len).float().unsqueeze(1)
        div_term = (torch.arange(0, dim, 2).float() * -(math.log(10000.0) / dim)).exp()

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        return self.pe[:, :x.shape[-2]]


class LearnablePositionalEmbedding(nn.Module):
    def __init__(self, dim, max_len=512):
        super().__init__()
        self.embedding = nn.Embedding(max_len, dim)
        self.register_buffer('range', torch.arange(max_len))

    def forward(self, x):
        return self.embedding(self.range[:x.size(-2)])