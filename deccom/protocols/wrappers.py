# cuz i am slim shady, the slimmiest of shadies, all you other limidadies are just imitating... idk i am not a wrapper

def bindto(attr):
        def outer(fn):
            
            def inner(*args, **kwargs):
                return fn(*args, **kwargs)
            
            inner.bindto = attr
            return inner
            
        return outer
def bindfrom(attr):
        def outer(fn):
            
            def inner(*args, **kwargs):
                return fn(*args, **kwargs)
            
            inner.bindfrom = attr
            return inner
        return outer
def nobind(fn):
    def inner(*args, **kwargs):
        return fn(*args, **kwargs)
    inner.nobind = "nobind"
    return inner