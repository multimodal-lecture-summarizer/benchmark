"""Python network denial during loading; not OS-level native-network isolation."""
from contextlib import contextmanager
import socket


@contextmanager
def deny_network():
    attempts=[]
    def denied(*args,**kwargs):
        attempts.append('Python socket/DNS network API called')
        raise RuntimeError('network disabled during frozen runtime loading')
    targets=[(socket,'create_connection'),(socket,'getaddrinfo'),
             (socket.socket,'connect'),(socket.socket,'connect_ex')]
    originals=[(obj,name,getattr(obj,name)) for obj,name in targets]
    try:
        for obj,name,_ in originals:
            setattr(obj,name,denied)
        yield attempts
    finally:
        for obj,name,original in originals:
            setattr(obj,name,original)
