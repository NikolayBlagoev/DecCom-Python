from gpt_distributed import GPTStageFirst, GPTStageLast, GPTStageMiddle
from sys import argv
import asyncio
from deccom.cryptofuncs.hash import SHA256
from deccom.nodes import StreamNode
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.peerdiscovery import KademliaDiscovery
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
from trainingnode import TrainingNode
from trainingprotocol import TrainingProtocol
from task_datasets.qqp import get_glue_qqp_train_data_loader
from task_datasets.tokenizer import build_tokenizer
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
train_loader =None

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




protocol = DefaultProtocol()
gossip = KademliaDiscovery([],interval=5)
gossip.set_lower(protocol)
stream = StreamProtocol(False)
stream.set_lower(gossip)
net = None
n = Peer(("127.0.0.1", 10015), pub_key="1")
if argv[1] == "0" or argv[1] == "3":
    tokenizer, leng = build_tokenizer()
    train_loader = get_glue_qqp_train_data_loader(tokenizer)
    if argv[1]!="0":
        gossip.bootstrap_peers.append(n)
    net = GPTStageFirst(1024,tokenizer.vocab_size, 2, "cpu")
elif argv[1] == "1" or argv[1] == "4":
    gossip.bootstrap_peers.append(n)
    tokenizer, leng = build_tokenizer()
    net = GPTStageMiddle(1024, -1, 2, "cpu")
    
elif argv[1] == "2" or argv[1] == "5":
    gossip.bootstrap_peers.append(n)
    tokenizer, leng = build_tokenizer()
    net = GPTStageLast(1024, tokenizer.vocab_size, 2, "cpu")

optimizer = optim.SGD(net.parameters(), lr=learning_rate,
                      momentum=momentum)
training = TrainingProtocol(3,3,int(argv[1]),net,optimizer,train_loader)
training.set_lower(stream)
me = TrainingNode(training,"127.0.0.1", 10015 if argv[1] == "0" else None)
print( "TCP", me.tcp_port)
self.peer = Peer((me.ip_addr,me.port), tcp=me.tcp_port, pub_key=argv[1])
print(self.peer.id_node)
loop = asyncio.new_event_loop()
print("run...")

loop.run_until_complete(me.listen())
loop.run_forever()