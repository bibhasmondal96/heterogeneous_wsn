import random
from .rpl import RPL
from .aodv import AODV

class NodeRPL(RPL):
    def __init__(self,addr,power,dist_range,print_func):
        coor = [random.randint(*dist_range), random.randint(*dist_range)]
        super(NodeRPL,self).__init__(addr,coor,power,print_func)
        self.print = print_func

class NodeAODV(AODV):
    def __init__(self,addr,power,dist_range,print_func):
        coor = [random.randint(*dist_range), random.randint(*dist_range)]
        super(NodeAODV,self).__init__(addr,coor,power,print_func)
        self.print = print_func