import time
import socket
import random
import threading
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class RPL(threading.Thread):

    transfer_loss = {"send":0.005,"receive":0.002}
    transfer_threshold = {"send": 1.5, "receive": 0.5}
    metric = {'dist':-0.01,'rank': -1.0,'power':0.0}
    INF = 999
    MAX_ATTEMPT = 100
    ATTEMPT_WAIT_TIME = 0.2
    BEST_PATH_WAIT_TIME = 3

    def __init__(self,addr,coor,power):
        super(RPL,self).__init__()
        self.addr = addr
        self.coor = coor #[x,y]
        self.node_id = "%s:%s"%addr
        self.range_const = 0.05
        self.dis_id = 0
        self.dag_id = 0
        self.init_power = power
        self.rem_power = power
        self.rank = None
        self.dist = None
        self.sent_bytes = 0
        self.received_bytes = 0
        self.dis_id_list = {}
        self.parents = {}
        self.childs = {}
        self.timers = {}
        self.best_parent = {} #{'dag_id':dag_id,'node_id':node_id,'score':score,'is_best':0}
        self.msg_box = {} #{'msg_data':msg_data,'is_read':0}
        self.pending_msg_q = {} #{'orig':self.node_id,'msg_data':msg_data}
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
            threading.Thread(target=self.parent_handler,args=('%s:%s'%node,)).start()

    def parent_handler(self,parent):       
        try:
            self.listener(self.parents[parent])
        except:
            sock = self.parents.pop(parent,None)
            if sock:sock.close()
            self.best_parent.pop(parent,None)

    def max_byte(self,operation):
        avail_pow = self.rem_power-self.transfer_threshold[operation]
        byte = avail_pow/self.transfer_loss[operation]
        return int(byte)

    def power_loss(self,message,op):
        loss = len(message)*self.transfer_loss[op]
        return loss

    def readline(self,sock):
        data = sock.recv(1)
        while b'\r\n' not in data:
            data += sock.recv(1)
        return data.decode()

    def listener(self,sock):
        while True:
            message = self.readline(sock)
            if message:
                if message[:4] == 'USER':
                    if len(message)<=self.max_byte('receive'):
                        # Update params
                        self.received_bytes += len(message)
                        self.rem_power -= self.power_loss(message,'receive')
                        self.on_recv(message)
                    else:
                        print('Low power')
                else:
                    self.on_recv(message)

    def on_recv(self,message):
        message = message.split('|')
        # Process message
        switch = {'DIS':self.process_dis,
                  'DIO':self.process_dio,
                  'USER': self.process_msg}
        switch[message[0]](message)

    def send(self,sock,message):
        if message[:4] != 'USER':
            # send message
            sock.send(message.encode())
        else:
            if len(message)<=self.max_byte('send'):
                # send message
                sock.send(message.encode())
                # Update params
                self.sent_bytes += len(message)
                self.rem_power -= self.power_loss(message,'send')
            else:
                print('Low power')

    def distance(self,coor):
        dx = float(coor[0])-self.coor[0]
        dy = float(coor[1])-self.coor[1]
        return (dx**2+dy**2)**0.5

    def is_neighbour(self,coor):
        if self.distance(coor)<=self.range_const*self.rem_power**2:
            return True
        return False

    def set_best_parent(self,sink):
        # Check whether sink is deleted for other nodes
        if sink in self.best_parent:
            self.best_parent[sink]['is_best'] = 1

    def send_dis(self,dest):
        '''Broadcast an DIS message'''
        self.dis_id += 1
        message = 'DIS|%s|%s|%s|\r\n'%(self.dis_id,self.node_id,dest)
        for parent in list(self.parents):
            # Check key exist or not due to dictionary change size during iteration
            if parent in self.parents:self.send(self.parents[parent],message)

    def process_dis(self,message):
        '''Process an incoming DIS request'''
        dis_id = message[1]
        orig = message[2]
        dest = message[3]
        if self.node_id == orig:
            return
        if orig in self.dis_id_list:
            # Discard duplicate DIS mesage
            if self.dis_id_list[orig] == dis_id:
                return
        # Buffer dis id
        self.dis_id_list[orig] = dis_id

        if self.node_id == dest:
            # Send DIO
            self.send_dio()
        else :
            self.forward_dis(message)

    def forward_dis(self,message):
        '''Rebroadcast an DIS request'''
        message = '|'.join(message)
        for parent in list(self.parents):
            # Check key exist or not due to dictionary change size during iteration
            if parent in self.parents:self.send(self.parents[parent],message)

    def send_dio(self,dag_id=None,orig=None,rank=0,dist=0,power=None):
        '''Broadcast an DIO message'''
        if not rank:self.dag_id += 1
        dag_id = dag_id or self.dag_id
        orig = orig or self.node_id
        self.rank = rank # rank from sink
        self.dist = dist # distance from sink
        power = power or self.INF
        message = 'DIO|%s|%s|%s|%s,%s|%s|%s|%s|\r\n'%(dag_id,orig,self.node_id,*self.coor,self.rank,self.dist,power)
        for node in self.childs:
            self.send(self.childs[node],message)

    def process_dio(self,message):
        '''Process an incoming DIO message'''
        dag_id = int(message[1])
        orig = message[2]
        sender = message[3]
        coor = message[4].split(',')
        rank = int(message[5])+1
        dist = float(message[6])+self.distance(coor)
        power = min(float(message[7]),self.rem_power)
        
        # return if current node is sink
        if self.node_id==orig:return
        
        # Restart timer on getiing rreq
        if orig in self.timers:
            # Cancel previous timer
            self.timers[orig].cancel()

        score = self.obj_func({'dist':dist,'power':power,'rank':rank})

        if orig not in self.best_parent:
            self.best_parent[orig] = {
                'dag_id':dag_id,
                'node_id':sender,
                'score':score,
                'is_best':0
            }
        elif self.best_parent[orig]['dag_id'] < dag_id:
            # Update best parent for current dag
            self.best_parent[orig] = {
                'dag_id':dag_id,
                'node_id':sender,
                'score':score,
                'is_best':0
            }
        elif self.best_parent[orig]['score'] < score:
            # Update best parent
            self.best_parent[orig] = {
                'dag_id':dag_id,
                'node_id':sender,
                'score':score,
                'is_best':0
            }
        else:
            # Add timer
            self.timers[orig] = threading.Timer(self.BEST_PATH_WAIT_TIME,self.set_best_parent,[orig,])
            # Start timer
            self.timers[orig].start()
            return
        # Send DIO if best parent updated
        self.send_dio(dag_id,orig,rank,dist,power)
        # Add timer
        self.timers[orig] = threading.Timer(self.BEST_PATH_WAIT_TIME,self.set_best_parent,[orig,])
        # Start timer
        self.timers[orig].start()

    def obj_func(self,dictionary):
        score = 0
        for key in dictionary:
            if key in self.metric:
                score += dictionary[key]*self.metric[key]
            else:
                score += dictionary[key]
        return score

    def send_msg(self,dest,msg_data):
        '''Send an USER message'''
        message = 'USER|%s|%s|%s|\r\n'%(self.node_id,dest,msg_data)
        # Reset best path flag to 0
        if dest in self.best_parent:
            self.best_parent[dest]['is_best'] = 0
        # Broadcast DIS
        self.send_dis(dest)
        for _ in range(self.MAX_ATTEMPT):
            if dest in self.best_parent:
                # Wait until finding the best path
                if self.best_parent[dest]['is_best']:
                    best_parent = self.best_parent[dest]['node_id']
                    self.send(self.parents[best_parent],message)
                    # send pending msg if available
                    self.send_pending_msgs(dest)
                    return
            time.sleep(self.ATTEMPT_WAIT_TIME)
        if dest not in self.pending_msg_q:
            self.pending_msg_q[dest] = []
        self.pending_msg_q[dest].append({'orig':self.node_id,'msg_data':msg_data})

    def send_pending_msgs(self,dest):
        '''Send a pending USER message'''
        if dest in self.pending_msg_q:
            while self.pending_msg_q[dest]:
                if dest in self.best_parent:
                    msg = self.pending_msg_q[dest].pop(0)
                    orig = msg['orig']
                    msg_data = msg['msg_data']
                    message = 'USER|%s|%s|%s|\r\n'%(orig,dest,msg_data)
                    best_parent = self.best_parent[dest]['node_id']
                    self.send(self.parents[best_parent],message)
                else:
                    return
            self.pending_msg_q.pop(dest)

    def process_msg(self,message):
        '''Process an USER message'''
        orig = message[1]
        dest = message[2]
        msg_data = message[3]
        if self.node_id == dest:
            if orig not in self.msg_box:
                self.msg_box[orig] = []
            self.msg_box[orig].append({'msg_data':msg_data,'is_read':0})
            print('New message arrived from %s'%orig)
        else:
            self.forward_msg(message)

    def forward_msg(self,message):
        '''Resend an USER message'''
        orig = message[1]
        dest = message[2]
        msg_data = message[3]
        message = '|'.join(message)

        if dest in self.best_parent:
            best_parent = self.best_parent[dest]['node_id']
            self.send(self.parents[best_parent],message)
        else:
            if dest not in self.pending_msg_q:
                self.pending_msg_q[dest] = []
            self.pending_msg_q[dest].append({'orig':orig,'msg_data':msg_data})
            
    def child_handler(self,conn):
        try:self.listener(conn)
        except:pass

    def run(self):
        while True:
            try:
                conn , _ = self.sock.accept()
                self.childs[conn.recv(21).decode()] = conn
                threading.Thread(target=self.child_handler,args=(conn,)).start()
            except:
                print('Connection closed')
                break

class Node(RPL):
    def __init__(self,addr,power,dist_range):
        coor = [random.randint(*dist_range), random.randint(*dist_range)]
        super(Node,self).__init__(addr,coor,power)

class Network:

    MAX_ATTEMPT = 100
    ATTEMPT_WAIT_TIME = 0.2

    def __init__(self,no_of_node=30,initial_node_power=50,dist_range=[0,50],ip='127.0.0.1',start_port=8000):
        self.no_of_node = no_of_node
        self.nodes = {}
        for i in range(no_of_node):
            addr = (ip,start_port+i)
            self.nodes['%s:%s'%addr] = Node(addr,initial_node_power,dist_range)
            self.nodes['%s:%s'%addr].start()
        # Initilize neighbour
        self.init_neighbour()

    def init_neighbour(self):
        for node1 in self.nodes:
            for node2 in self.nodes:
                if node1 != node2:
                    if self.nodes[node1].is_neighbour(self.nodes[node2].coor):
                        if node1 not in self.nodes[node2].parents:
                            self.nodes[node2].connect(self.nodes[node1].addr)
                    else:
                        # Remove from childs and close conn
                        if node2 in self.nodes[node1].childs:
                            conn = self.nodes[node1].childs.pop(node2)
                            conn.close()

    def shutdown(self):
        for node in self.nodes.values():
            for child in node.childs.values():
                child.close()
            node.sock.close()

    def reset(self,factor):
        for node in self.nodes:
            self.nodes[node].metric = {'dist':-0.01,'rank': -1+factor,'power':factor}
            self.nodes[node].rem_power = self.nodes[node].init_power
            self.nodes[node].rank = None
            self.nodes[node].dist = None
            self.nodes[node].dis_id = 0
            self.nodes[node].dag_id = 0
            self.nodes[node].sent_bytes = 0
            self.nodes[node].received_bytes = 0
            self.nodes[node].dis_id_list = {}
            self.nodes[node].timers = {}
            self.nodes[node].best_parent = {}
            self.nodes[node].msg_box = {}
            self.nodes[node].pending_msg_q = {}

    def plot_transfer_stat(self,dest,no=1):
        transfer = []
        power_factor = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            print('%s%s%s'%('-'*18,i,'-'*18))
            total = 0
            self.reset(i)               
            self.start_session(dest,no)
            for name,node in self.nodes.items():
                total += node.received_bytes+node.sent_bytes
            transfer.append(total/self.no_of_node)
            power_factor.append(i)
        plt.figure(figsize=(30,15),dpi=200)
        plt.plot(power_factor,transfer)
        plt.xlabel('Power Factor')
        plt.ylabel('Energy Transfer')
        plt.title("Energy Transfer vs Power Factor", fontsize='large')
        plt.show()

    def plot_neighbour_connection(self):
        for node in self.nodes:
            for child in self.nodes[node].childs:
                x = [self.nodes[node].coor[0],self.nodes[child].coor[0]]
                y = [self.nodes[node].coor[1],self.nodes[child].coor[1]]
                plt.plot(x, y, '-o')

    def plot_dest_connection(self,dest):
        self.init_neighbour()
        for node in self.nodes.values():
            if dest in node.best_parent:
                node.best_parent[dest]['is_best'] = 0
        self.nodes[dest].send_dio()
        for node in self.nodes.values():
            for _ in range(self.MAX_ATTEMPT):
                if dest in node.best_parent:
                    if node.best_parent[dest]['is_best']:
                        best_parent = self.nodes[node.best_parent[dest]['node_id']]
                        x = [best_parent.coor[0],node.coor[0]]
                        y = [best_parent.coor[1],node.coor[1]]
                        plt.plot(x, y, '-o')
                        break
                time.sleep(self.ATTEMPT_WAIT_TIME)

    def plot_network(self):
        x=[]
        y=[]
        c=[]
        s=[]
        plt.figure(figsize=(30,15),dpi=200)
        for node in self.nodes.values():
            x.append(node.coor[0])
            y.append(node.coor[1])
            c.append(node.rem_power/node.init_power)
            s.append(3.14*25**2) # mult 8.1
            plt.text(x[-1], y[-1],node.node_id,size=20,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6,picker=True)
        plt.grid(True)

    def start_session(self,dest,no=1):
        count = 0
        while count != no or no==-1: # -1 for infinite
            for node in self.nodes:
                if node != dest:
                    sent = False
                    self.init_neighbour()
                    self.nodes[node].send_msg(dest,'PING')
                    # Check whether msg reaches to dest
                    for _ in range(self.MAX_ATTEMPT):
                        if node in self.nodes[dest].msg_box:
                            if not self.nodes[dest].msg_box[node][-1]['is_read']:
                                self.nodes[dest].msg_box[node][-1]['is_read'] = 1
                                sent = True
                                break
                        time.sleep(self.ATTEMPT_WAIT_TIME)
                    if not sent:
                        return count
            count += 1

    def gini_coefficient(self):
        x = []
        y = []
        for i,node1 in enumerate(self.nodes):
            neighbours_power = []
            for node2 in self.nodes:
                if node1 != node2:
                    if self.nodes[node1].is_neighbour(self.nodes[node2].coor):
                        neighbours_power.append(self.nodes[node2].rem_power)
            y.append(sum(neighbours_power))
            x.append((i+1)/len(self.nodes))
        y.sort()
        b = y.copy()
        n = len(self.nodes)
        T = sum(y)
        x = [0]+x
        y = [0]+[sum(y[:i])/T for i in range(1,len(y)+1)]
        # Caluclating gini coeff
        polygon_area = (1/(n*T))*sum([(n-i+1/2)*b[i-1] for i in range(1,n+1)])
        gini_coefficient = 1-2*polygon_area
        return gini_coefficient

    def plt_lorentz_curve(self):
        x = []
        y = []
        for i,node1 in enumerate(self.nodes):
            neighbours_power = []
            for node2 in self.nodes:
                if node1 != node2:
                    if self.nodes[node1].is_neighbour(self.nodes[node2].coor):
                        neighbours_power.append(self.nodes[node2].rem_power)
            y.append(sum(neighbours_power))
            x.append((i+1)/len(self.nodes))
        y.sort()
        b = y.copy()
        n = len(self.nodes)
        T = sum(y)
        x = [0]+x
        y = [0]+[sum(y[:i])/T for i in range(1,len(y)+1)]
        # Caluclating gini coeff
        polygon_area = (1/(n*T))*sum([(n-i+1/2)*b[i-1] for i in range(1,n+1)])
        gini_coefficient = 1-2*polygon_area
        # Lorenz curve
        plt.figure(figsize=(30,15),dpi=200)
        plt.plot(x,y,label="Lorenz curve")
        # Line of perfect equality
        plt.plot([x[0],x[-1]],[y[0],y[-1]],label="Line of perfect equality")
        # Line of perfect inequality
        plt.plot([x[0],x[-1],x[-1]],[y[0],y[0],y[-1]],color='black',label="Line of perfect inequality")
        plt.text(0.2, 0.7,"Gini coefficient: %s"%round(giniCoefficient,2),horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.xlabel('Nodes(%)')
        plt.ylabel('Energy(%)')
        ticks = list(map(lambda v:v/100,range(0,101,10)))
        plt.title("Energy(%) vs Nodes(%)", fontsize='large')
        plt.xticks(ticks,ticks)
        plt.yticks(ticks,ticks)
        plt.grid(True)
        plt.legend()

    def plot_gini_stat(self,dest,no=1):
        gini_index = []
        power_factor = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            print('%s%s%s'%('-'*18,i,'-'*18))
            self.reset(i)
            self.start_session(dest,no)
            gini_index.append(self.gini_coefficient())
            power_factor.append(i)
        plt.figure(figsize=(30,15),dpi=200)
        plt.plot(power_factor,gini_index)
        plt.xlabel('Power Factor')
        plt.ylabel('Gini Coefficient')
        plt.title("Gini Coefficient vs Power Factor", fontsize='large')
        plt.show()

    def plot_max_session(self,dest):
        max_session = []
        power_factor = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            print('%s%s%s'%('-'*18,i,'-'*18))
            self.reset(i)
            max_session.append(self.start_session(dest,-1))
            power_factor.append(i)
        plt.figure(figsize=(30,15),dpi=200)
        plt.plot(power_factor,max_session)
        plt.xlabel('Power Factor')
        plt.ylabel('No of session')
        plt.title("Max no of session vs Power Factor", fontsize='large')
        plt.grid(True)
        plt.show()

    def plot_energy_stat(self,dest,no=1):
        x = np.arange(0.0,1.2, 0.2)
        y = np.arange(0.1,1.0, 0.1)
        y, x = np.meshgrid(y,x)
        z = np.zeros_like(y)
        for i,factor in enumerate(x[:,0]):
            print('%s%s%s'%('-'*18,round(factor,1),'-'*18))
            self.reset(factor)
            self.start_session(dest,no)
            for node in self.nodes.values():
                for j,percent in enumerate(y[0]):
                    if node.rem_power/node.init_power <= percent:
                        z[i][j] += 1
        x,y,z = x.ravel(),y.ravel(),z.ravel()
        b = np.zeros_like(z)
        c = list(map(lambda y:plt.cm.RdYlGn(y),y))
        fig = plt.figure(figsize=(30,15),dpi=200)
        ax = fig.gca(projection='3d')
        ax.bar3d(x,y, b, 0, 0.05, z, shade=True,color=c, alpha=0.8)
        ax.set_zlabel('No of nodes')
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('Remaining Energy')
        plt.grid(True)
        plt.show()

try:network.shutdown()
except:pass
network = Network()
network.plot_network()
network.plot_neighbour_connection()
network.plot_network()
network.plot_dest_connection('127.0.0.1:8029')
network.reset(0.0)
network.start_session('127.0.0.1:8029',-1)
network.plot_transfer_stat('127.0.0.1:8029',3)
network.plot_gini_stat('127.0.0.1:8029',3)
network.plot_max_session('127.0.0.1:8029')
network.plot_energy_stat('127.0.0.1:8029',3)
network.nodes['127.0.0.1:8029'].msg_box