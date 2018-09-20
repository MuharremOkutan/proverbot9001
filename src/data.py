#!/usr/bin/env python3

from tokenizer import Tokenizer, TokenizerState, get_topk_keywords, get_relevant_k_keywords
from format import read_tuple
from models.components import SimpleEmbedding
import re

from typing import Tuple, List, Callable
from util import *
from context_filter import ContextFilter
from serapi_instance import get_stem

Sentence = List[int]
Bag = List[int]
RawDataset = List[Tuple[List[str], str, str]]
ClassifySequenceDataset = List[Tuple[Sentence, int]]
SequenceSequenceDataset = List[Tuple[Sentence, Sentence]]
ClassifyBagDataset = List[Tuple[Bag, int]]

def getTokenbagVector(goal : Sentence) -> Bag:
    tokenbag: List[int] = []
    for t in goal:
        if t >= len(tokenbag):
            tokenbag = extend(tokenbag, t+1)
        tokenbag[t] += 1
    return tokenbag

def extend(vector : List[int], length : int):
    assert len(vector) <= length
    return vector + [0] * (length - len(vector))

def read_text_data(data_path : str,  max_size:int=None) -> RawDataset:
    data_set = []
    with open(data_path, mode="r") as data_file:
        t = read_tuple(data_file)
        counter = 0
        while t and (not max_size or counter < max_size):
            hyps, context, tactic = t
            counter += 1
            data_set.append((hyps, context, tactic))
            t = read_tuple(data_file)
    assert len(data_set) > 0
    return data_set

def filter_data(data : RawDataset, pair_filter : ContextFilter) -> RawDataset:
    return [(hyps, goal, tactic)
            for ((hyps, goal, tactic), (next_hyps, next_goal, next_tactic)) in
            zip(data, data[1:])
            if pair_filter({"goal": goal, "hyps" : hyps}, tactic,
                           {"goal": next_goal, "hyps" : next_hyps})]

def make_keyword_tokenizer(data : List[str],
                           tokenizer_type : Callable[[List[str], int], Tokenizer],
                           num_keywords : int,
                           num_reserved_tokens : int) -> Tokenizer:
    keywords = get_topk_keywords(data, num_keywords)
    tokenizer = tokenizer_type(keywords, num_reserved_tokens)
    return tokenizer

def encode_seq_seq_data(data : RawDataset,
                        context_tokenizer_type : Callable[[List[str], int], Tokenizer],
                        tactic_tokenizer_type : Callable[[List[str], int], Tokenizer],
                        num_keywords : int,
                        num_reserved_tokens : int) \
    -> Tuple[SequenceSequenceDataset, Tokenizer, Tokenizer]:
    context_tokenizer = make_keyword_tokenizer([context for hyps, context, tactic in data],
                                               context_tokenizer_type,
                                               num_keywords, num_reserved_tokens)
    tactic_tokenizer = make_keyword_tokenizer([tactic for hyps, context, tactic in data],
                                              tactic_tokenizer_type,
                                              num_keywords, num_reserved_tokens)
    result = [(context_tokenizer.toTokenList(context),
               tactic_tokenizer.toTokenList(tactic))
              for hyps, context, tactic in data]
    context_tokenizer.freezeTokenList()
    tactic_tokenizer.freezeTokenList()
    return result, context_tokenizer, tactic_tokenizer

def encode_seq_classify_data(data : RawDataset,
                             tokenizer_type : Callable[[List[str], int], Tokenizer],
                             num_keywords : int,
                             num_reserved_tokens : int) \
    -> Tuple[ClassifySequenceDataset, Tokenizer, SimpleEmbedding]:
    embedding = SimpleEmbedding()
    keywords = get_relevant_k_keywords([(context, embedding.encode_token(get_stem(tactic)))
                                        for hyps, context, tactic in data][:1000],
                                       num_keywords)
    tokenizer = tokenizer_type(keywords, num_reserved_tokens)
    result = [(tokenizer.toTokenList(context), embedding.encode_token(get_stem(tactic)))
              for hyps, context, tactic in data]
    tokenizer.freezeTokenList()
    return result, tokenizer, embedding

def encode_bag_classify_data(data : RawDataset,
                             tokenizer_type : Callable[[List[str], int], Tokenizer],
                             num_keywords : int,
                             num_reserved_tokens : int) \
    -> Tuple[ClassifyBagDataset, Tokenizer, SimpleEmbedding]:
    seq_data, tokenizer, embedding = encode_seq_classify_data(data, tokenizer_type,
                                                              num_keywords,
                                                              num_reserved_tokens)
    bag_data = [(extend(getTokenbagVector(context), tokenizer.numTokens()), tactic)
                for context, tactic in seq_data]
    return bag_data, tokenizer, embedding

def encode_bag_classify_input(context : str, tokenizer : Tokenizer ) \
    -> Bag:
    return extend(getTokenbagVector(tokenizer.toTokenList(context)), tokenizer.numTokens())