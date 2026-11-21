"""Reproduction of the pandas 3.0.0 hash_pandas_object fault that made the r16 cross-source duplicate rule match nothing (PRD, Cleaning section 1).
  python3 r16/repro_hash_bug.py   (pandas 3.0.0: two different keys share one hash and the same key hashes differently in another Series; 3.1.1: correct)"""
import pandas as pd
h = lambda l: pd.util.hash_pandas_object(pd.Series(l), index=False).tolist()
print(pd.__version__)
print("one Series, two different keys:        ", h(["GET\0/a\0x", "GET\0/b\0y"]))
print("same key 'GET\\0/b\\0y', Series 1:       ", h(["GET\0/a\0x", "GET\0/b\0y"])[1])
print("same key 'GET\\0/b\\0y', Series 2:       ", h(["GET\0/aaaaaa\0x", "GET\0/b\0y"])[1])
print("same key without NUL separator, S1 / S2:", h(["GET /a x", "GET /b y"])[1], h(["GET /aaaaaa x", "GET /b y"])[1])
