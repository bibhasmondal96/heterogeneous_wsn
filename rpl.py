import time
import math
import socket
import random
import threading
import matplotlib.pyplot as plt
class RPL(threading.Thread):
    
    transfer_loss = {"send":0.005,"receive":0.002}
    transfer_threshold = {"send": 1.5, "receive": 0.5}
    metric = {'dist':-1,'rank': -0.50,'power':0.50}
    ATTEMPT_TIME = 1
    MAX_ATTEMPT = 10

    def __init__(self,addr,coor):
        super(RPL,self).__init__()
        self.addr = addr
        self.coor = coor #[x,y]
        self.node_id = "%s:%s"%addr
        self.power = 5
        self.rank = None
        self.dist = None
        self.sent_bytes = 0
        self.received_bytes = 0
        self.parents = {}
        self.childs = {}
        self.best_parent = {} #{'node_id':node_id,'score':score}
        self.msg_box = {}
        self.pending_msg_q = {}
        self.sock = socket.socket()
        self.sock.bind(addr)
        self.sock.listen(5)
        
    def connect(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            s = socket.socket()
            s.connect(node)
            s.send(self.node_id.encode())
            self.parents['%s:%s'%node] = s
            threading.Thread(target=self.listener,args=(s,)).start()
            
    def max_byte(self,operation):
        avail_pow = self.power-self.transfer_threshold[operation]
        byte = avail_pow/self.transfer_loss[operation]
        return int(byte)
    
    def power_loss(self,message,op):
        loss = len(message)*self.transfer_loss[op]
        return loss

    def listener(self,sock):
        with sock:
            f = sock.makefile(mode='r')
            while True:
                message = f.readline()
                if message:
                    if message[:3] != 'DIO':
                        if len(message)<=self.max_byte('receive'):
                            print('Received %s bytes'%len(message))
                            # Update params
                            self.received_bytes += len(message)
                            self.power -= self.power_loss(message,'receive')
                            self.on_recv(message)
                        else:
                            print('Low power')
                    else:
                        self.on_recv(message)
                        
    
    def on_recv(self,message):
        message = message.split('|')
        # Process message
        switch = {'DIO':self.process_dio,
                  'MSG': self.process_msg}
        switch[message[0]](message)
        
    def send(self,sock,message):
        if message[:3] == 'DIO':
            # send message
            sock.send(message.encode())
        else:
            if len(message)<=self.max_byte('send'):
                # send message
                sock.send(message.encode())
                # Update params
                self.sent_bytes += len(message)
                self.power -= self.power_loss(message,'send')
                print('Sent %s bytes'%len(message))
            else:
                print('Low power',self.power)
        
    def distance(self,coor):
        dx = float(coor[0])-self.coor[0]
        dy = float(coor[1])-self.coor[1]
        return math.sqrt(dx**2+dy**2)
    
    def send_dio(self,rank=0,dist=0):
        self.rank = rank # rank from sink
        self.dist = dist # distance from sink
        message = 'DIO|%s|%s,%s|%s|%s|%s|\r\n'%(self.node_id,*self.coor,self.rank,self.dist,self.power)
        for node in self.childs:
            self.send(self.childs[node],message)
    
    def process_dio(self,message):
        # return if current node is sink
        if self.rank==0:return
        sender = message[1]
        coor = message[2].split(',')
        rank = int(message[3])+1
        dist = float(message[4])+self.distance(coor)
        power = float(message[5])

        score = self.obj_func({'dist':dist,'power':power,'rank':rank})

        if not self.best_parent:
            self.best_parent['node_id'] = sender
            self.best_parent['score'] = score
        elif self.best_parent['score'] < score:
            # Update best parent
            self.best_parent['node_id'] = sender
            self.best_parent['score'] = score
        else:
            return
        # Send DIO if best parent updated
        self.send_dio(rank,dist)
    
    def obj_func(self,dictionary):
        score = 0
        for key in dictionary:
            if key in self.metric:
                score += dictionary[key]*self.metric[key]
            else:
                score += dictionary[key]
        return score
            
    
    def send_msg(self,dest,msg_data):
        message = 'MSG|%s|%s|%s|\r\n'%(self.node_id,dest,msg_data)
        if self.best_parent:
            best_parent = self.best_parent['node_id']
            self.send(self.parents[best_parent],message)
        else:
            self.pending_msg_q[dest] = {'orig':self.node_id,'msg_data':msg_data}
        
        # Try to send pending msg if available
        for _ in range(self.MAX_ATTEMPT):
            if self.pending_msg_q:
                self.send_pending_msgs()
                time.sleep(self.ATTEMPT_TIME)
            else:
                break
    
    def send_pending_msgs(self):
        if self.best_parent:
            for dest in list(self.pending_msg_q):
                msg = self.pending_msg_q.pop(dest)
                orig = msg['orig']
                msg_data = msg['msg_data']
                message = 'MSG|%s|%s|%s|\r\n'%(orig,dest,msg_data)
                best_parent = self.best_parent['node_id']
                self.send(self.parents[best_parent],message)
    
    def process_msg(self,message):
        orig = message[1]
        dest = message[2]
        msg_data = message[3]
        if self.node_id == dest:
            self.msg_box[orig] = msg_data
            print('New message arrived')
        else:
            self.forward_msg(message)
    
    def forward_msg(self,message):
        orig = message[1]
        dest = message[2]
        msg_data = message[3]
        message = '|'.join(message)

        if self.best_parent:
            best_parent = self.best_parent['node_id']
            self.send(self.parents[best_parent],message)
        else:
            self.pending_msg_q[dest] = {'orig':orig,'msg_data':msg_data}
  
    def run(self):
        while True:
            try:
                conn , _ = self.sock.accept()
                self.childs[conn.recv(21).decode()] = conn
                threading.Thread(target=self.listener,args=(conn,)).start()
            except:
                print('Connection closed\n')
                break
class Node(RPL):
    def __init__(self,addr,dist_range=[1,50]):
        coor = [random.randint(*dist_range), random.randint(*dist_range)]
        super(Node,self).__init__(addr,coor)
class Network:
    def __init__(self,no_of_node,ip='127.0.0.1',start_port=8000):
        self.no_of_node = no_of_node
        self.nodes = {}
        for i in range(no_of_node):
            addr = (ip,start_port+i)
            self.nodes['%s:%s'%addr] = Node(addr)
            self.nodes['%s:%s'%addr].start()
        # Initilize neighbour
        self.init_neighbour()

    def init_neighbour(self):
        for node in self.nodes:
            self.nodes[node].parents = {}
            self.nodes[node].childs = {}
        for node1 in self.nodes:
            for node2 in self.nodes:
                if self.nodes[node1].distance(self.nodes[node2].coor) <= self.nodes[node1].power**2 and node1 != node2:
                    self.nodes[node1].connect(self.nodes[node2].addr)
                    
    def shutdown(self):
        for node in self.nodes.values():
            node.sock.close()
            for parent in node.parents.values():
                parent.close()
                
    def reset(self,factor):
        for node in self.nodes:
            self.nodes[node].metric = {'dist':-1,'rank': -1+factor,'power':factor}
            self.nodes[node].power = 5
            self.nodes[node].rank = None
            self.nodes[node].dist = None
            self.nodes[node].sent_bytes = 0
            self.nodes[node].received_bytes = 0
            self.nodes[node].best_parent = {}
            self.nodes[node].msg_box = {}
            self.nodes[node].pending_msg_q = {}
                    
    def plot_transfer_stat(self,dest):
        transfer = []
        power = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            total = 0
            self.reset(i)               
            self.start_season(dest)
            for name,node in self.nodes.items():
                total += node.received_bytes+node.sent_bytes
            transfer.append(total/self.no_of_node)
            power.append(i)
        plt.plot(power,transfer)
        plt.show()
                    
    def plot_neighbour_connection(self):
        for node in self.nodes:
            for child in self.nodes[node].childs:
                x = [self.nodes[node].coor[0],self.nodes[child].coor[0]]
                y = [self.nodes[node].coor[1],self.nodes[child].coor[1]]
                plt.plot(x, y, '-o')
                
    def plot_best_parent_connection(self):
        for node in self.nodes.values():
            if node.best_parent:
                best_parent = self.nodes[node.best_parent['node_id']]
                x = [best_parent.coor[0],node.coor[0]]
                y = [best_parent.coor[1],node.coor[1]]
                plt.plot(x, y, '-o')
                    
    def plot_network(self):
        x=[]
        y=[]
        c=[]
        s=[]
        plt.figure(figsize=(30,15),dpi=200)
        for node in self.nodes.values():
            x.append(node.coor[0])
            y.append(node.coor[1])
            c.append(node.power)
            s.append(3.14*25**2) # mult 8.1
            plt.text(x[-1], y[-1],node.node_id,size=20,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6,picker=True)
        plt.grid(True)

    def start_season(self,dest):
        for node in self.nodes:
            if node != dest:
                self.nodes[dest].send_dio()
                self.nodes[node].send_msg(dest,'PING')
                time.sleep(0.5)
                self.init_neighbour()
network.shutdown()
network = Network(10)
network.plot_network()
network.plot_neighbour_connection()
network.nodes['127.0.0.1:8009'].send_dio()
network.plot_network()
network.plot_best_parent_connection()
network.plot_transfer_stat('127.0.0.1:8009')
network.nodes['127.0.0.1:8009'].msg_box