from typing import Any, Callable
from deccom.peers.peer import Peer
from deccom.protocols.defaultprotocol import DefaultProtocol
class AbstractProtocol(object):
    required_lower = ["sendto", "start", "callback"]
    offers = {  
                "sendto": "sendto",
                "callback": "callback",
                "process_datagram": "process_datagram",
                }
    bindings = dict({"_lower_start":  "start", "_lower_sendto":  "sendto", "process_datagram": "set_callback"})
    

    def check_if_have(submodule, attr)->bool:
        
        if not hasattr(submodule,attr):
            if hasattr(submodule,"offers"):
                if isinstance(submodule.offers, dict):
                    if submodule.offers.get(attr) != None:
                        if submodule._taken.get(submodule.offers.get(attr)) != None:
                            raise Exception(attr,"already taken by",submodule._taken.get(submodule.offers.get(attr)))
                        return True
            if not hasattr(submodule,"submodule") or submodule.submodule == None:
                return False
            else:
                return AbstractProtocol.check_if_have(submodule.submodule,attr)
            
        else:
            if submodule._taken.get(attr) != None:
                raise Exception(attr,"already taken by",submodule._taken.get(attr))
            return True
        
        
        return True
    def get_if_have(submodule: Any, attr)->bool:
        if not hasattr(submodule,attr):
            if hasattr(submodule,"offers"):
                if isinstance(submodule.offers, dict):
                    if submodule.offers.get(attr) != None:
                        return getattr(submodule,submodule.offers.get(attr))
            if not hasattr(submodule,"submodule") or submodule.submodule == None:
                return None
            else:
                return AbstractProtocol.get_if_have(submodule.submodule,attr)
        else:
            return getattr(submodule,attr)
        return None
    def set_if_have(submodule,attr,val):
        
        if not hasattr(submodule,attr):
            if hasattr(submodule,"offers"):
                if isinstance(submodule.offers, dict):
                    if submodule.offers.get(attr) != None:
                        if submodule._taken.get(submodule.offers.get(attr)) != None:
                            raise Exception(attr,"already taken by",submodule._taken.get(attr))
                        # print("found",attr,"at",submodule, submodule.offers.get(attr))
                        getattr(submodule,submodule.offers.get(attr))(val)
                        submodule._taken[submodule.offers.get(attr)] = val
                        return
            if not hasattr(submodule,"submodule") or submodule.submodule == None:
                raise Exception("Cannot find any method to bind to",attr)
            else:
                AbstractProtocol.set_if_have(submodule.submodule,attr,val)
        else:
            if submodule._taken.get(attr) != None:
                raise Exception(attr,"already taken by",submodule._taken.get(attr))
            # print("found",attr,"at",submodule)
            getattr(submodule,attr)(val)
            submodule._taken[attr] = val
            return
        raise Exception("Cannot find any method to bind to",attr)
    def __init__(self, submodule = None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: ...):
        self.started = False
        self.submodule = submodule
        self.callback = callback
        self._taken = dict()
        self._lower_sendto = lambda msg,addr: ...
        self._lower_start = lambda: ...
        
    def process_datagram(self,addr:tuple[str,int],data:bytes):
        self.callback(addr,data)
        return

        
    async def start(self):
        await self._lower_start()
        print("started")
        self.started = True
    
    def inform_lower(self):
        # print("lower setting")
        for k,v in self.__class__.bindings.items():
            method = self.__class__.get_if_have(self.submodule,v)
            if method == None:
                continue
            else:
                if k[0] == "_":
                    setattr(self,k,method)
                    # print("setting",k,"to",method)
                    if self.__class__.offers.get(v) and not hasattr(self,v):
                        setattr(self, v, lambda self,**kwargs: method(self,**kwargs))
                        # print("setting to ",self, v, "to", method)
                    
                        
                else:
                    self.__class__.set_if_have(self.submodule,v,getattr(self,k))
                    

    def set_lower(self, submodule):
        self.submodule = submodule
        for method in self.__class__.required_lower:
            if not self.__class__.check_if_have(submodule,method): 
                raise Exception("MISSING REQUIRED!",method," in the protocol chain by ",type(self))
        
        self.inform_lower()
    def get_lowest(self):
        return self.submodule.get_lowest()
    def set_callback(self, callback):
        self.callback = callback
    async def sendto(self,msg,addr):
        await self._lower_sendto(msg,addr)
    def __getattribute__(self, __name: str) -> Any:
        
            
        try:
                # print("looking for", __name,self)
                return object.__getattribute__(self, __name)
        except AttributeError:
                if not self.started:
                    raise AttributeError()
                else:
                    # print("missing",self, __name)
                    return self.submodule.__getattribute__(__name)
        