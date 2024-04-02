from deccom.protocols.delayprotocol import DelayProtocol
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from gpt_distributed import GPTStageFirst, GPTStageLast, GPTStageMiddle
from sys import argv
import asyncio
from deccom.cryptofuncs.hash import SHA256
from deccom.nodes import StreamNode
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
from swarmprotocol import SwarmProtocol
from trainingnode import TrainingNode
from task_datasets.qqp import get_glue_qqp_train_data_loader
from task_datasets.tokenizer import build_tokenizer
import torchvision
import torch
n_epochs = 3
batch_size_train = 16
batch_size_test = 1000
learning_rate = 0.01
momentum = 0.5
log_interval = 10

random_seed = 1



# train_loader = torch.utils.data.DataLoader(
#   torchvision.datasets.MNIST('files/', train=True, download=True,
#                              transform=torchvision.transforms.Compose([
#                                torchvision.transforms.ToTensor(),
#                                torchvision.transforms.Normalize(
#                                  (0.1307,), (0.3081,))
#                              ])),
#   batch_size=batch_size_train, shuffle=True)

# test_loader = torch.utils.data.DataLoader(
#   torchvision.datasets.MNIST('files/', train=False, download=True,
#                              transform=torchvision.transforms.Compose([
#                                torchvision.transforms.ToTensor(),
#                                torchvision.transforms.Normalize(
#                                  (0.1307,), (0.3081,))
#                              ])),
#   batch_size=batch_size_test, shuffle=True)


import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import pickle
class Pipe0(nn.Module):
    def __init__(self):
        super(Pipe0, self).__init__()
        self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
        
        self.vc = [0] * 10
    def forward(self, x):
        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        
        return x
        
class Pipe1(nn.Module):
    def __init__(self):
        super(Pipe1, self).__init__()
        
        self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
        self.vc = [0] * 10
    def forward(self, x):
        x = F.relu(F.max_pool2d(self.conv2(x), 2))
        return x
        
class Pipe2(nn.Module):
    def __init__(self):
        super(Pipe2, self).__init__()
        
        self.fc1 = nn.Linear(320, 50)
        self.fc2 = nn.Linear(50, 10)
        self.vc = [0] * 10

    def forward(self, x):
        x = x.view(-1, 320)
        x = F.relu(self.fc1(x))
        
        x = self.fc2(x)
        return F.log_softmax(x)


delay_bandwidth_dict = {
    "0-1": (143, 0.007),
    "0-2": (172, 0.006),
    "0-3": (11, 0.007),
    "0-4": (100, 0.004),
    "0-5": (86, 0.010),
    "1-2": (34, 0.010),
    "1-3": (130, 0.006),
    "1-4": (223, 0.002),
    "1-5": (210, 0.002),
    "2-3": (159, 0.005),
    "2-4": (235, 0.003),
    "2-5": (238, 0.010),
    "3-4": (99, 0.003),
    "3-5": (86, 0.010),
    "4-5": (14, 0.011),
    


}
def delay_map(p1,p2):
    if delay_bandwidth_dict.get(p1+"-"+p2) != None:
        return delay_bandwidth_dict.get(p1+"-"+p2)
    else:
        delay_bandwidth_dict.get(p2+"-"+p1)
protocol = DefaultProtocol()
gossip = KademliaDiscovery([],interval=12)
gossip.set_lower(protocol)
stream = StreamProtocol(False)
stream.set_lower(gossip)
delayer= DelayProtocol(delay_map=delay_map)
delayer.set_lower(stream)
net = None
train_loader = None
n = Peer(("127.0.0.1", 10015))
if argv[1] != "0":
    gossip.bootstrap_peers.append(n)
loss_fn = None
get_data = None
def extract_data(loader):
    i, ret = next(loader)
    return ret['text'], ret['text']
if argv[1] == "0" or argv[1] == "6":
    
    tokenizer, leng = build_tokenizer()
    print(tokenizer.vocab_size)
    train_loader = get_glue_qqp_train_data_loader(tokenizer)
    net = GPTStageFirst(1024,tokenizer.vocab_size, 2, "cpu")
    loss_fn = net.task_layer
    get_data = lambda: extract_data(train_loader)
    
elif argv[1] == "5" or argv[1] == "11":
    
    tokenizer, leng = build_tokenizer()
    net = GPTStageLast(1024, tokenizer.vocab_size, 2, "cpu")
else:
    
    tokenizer, leng = build_tokenizer()
    net = GPTStageMiddle(1024, -1, 2, "cpu")

optimizer = optim.SGD(net.parameters(), lr=learning_rate,
                      momentum=momentum)
training = SwarmProtocol(pipeline_size=3, stage=int(argv[1])%3, net = net, optimizer=optimizer, max_iterations=10, microbatches=3)
training.set_lower(delayer)
me = TrainingNode( Peer(None, pub_key=argv[1]), training,"127.0.0.1", 10015 if argv[1] == "0" else None)
print( "TCP", me.tcp_port)

loop = asyncio.new_event_loop()
print("run...")

loop.run_until_complete(me.listen())
loop.run_forever()