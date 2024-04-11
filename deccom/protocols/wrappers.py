# cuz i am slim shady, the slimmiest of shadies, all you other limidadies are just imitating... idk i am not a wrapper

def bindto(attr, of_class = None, share = False):
        def outer(fn):
            
            def inner(*args, **kwargs):
                return fn(*args, **kwargs)
            
            inner.bindto = attr
            inner.share = share
            inner.of_class = of_class
            return inner
            
        return outer
def bindfrom(attr, of_class = None, share = False):
        def outer(fn):
            
            def inner(*args, **kwargs):
                return fn(*args, **kwargs)
            
            inner.bindfrom = attr
            inner.share = share
            inner.of_class = of_class
            return inner
        return outer
def nobind(fn):
    def inner(*args, **kwargs):
        return fn(*args, **kwargs)
    inner.nobind = "nobind"
    return inner