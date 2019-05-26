import random
from rpl import RPL

class Node(RPL):
    def __init__(self,addr,power,dist_range,print_func):
        coor = [random.randint(*dist_range), random.randint(*dist_range)]
        super(Node,self).__init__(addr,coor,power,print_func)
        self.print = print_func