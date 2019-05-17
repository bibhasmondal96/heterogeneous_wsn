import time
import socket
import random
import threading
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class AODV(threading.Thread):

    transfer_loss = {"send":0.005,"receive":0.002}
    transfer_threshold = {"send": 1.5, "receive": 0.5}
    metric = {'dist':-0.01,'hop': -1.0,'power':0.0}
    INF = 999
    MAX_ATTEMPT = 100
    ATTEMPT_WAIT_TIME = 0.2
    BEST_PATH_WAIT_TIME = 3

    def __init__(self,addr,coor,power):
        super(AODV,self).__init__()
        self.addr = addr
        self.coor = coor #[x,y]
        self.node_id = "%s:%s"%addr
        self.range_const = 0.05
        self.seq_no = 0
        self.init_power = power
        self.rem_power = power
        self.sent_bytes = 0
        self.received_bytes = 0
        self.parents = {}
        self.childs = {}
        self.routing_table = {}
        self.timers = {} #{'rreq_id':rreq_id,'timer':timer}
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
            for table in list(self.routing_table):
                if self.routing_table[table]['Next-Hop'] == parent:
                    self.routing_table.pop(table,None)

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
        switch = {'RREQ':self.process_rreq,
                  'RREP':self.process_rrep,
                  'USER': self.process_user_message}
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

    def obj_func(self,dictionary):
        score = 0
        for key in dictionary:
            if key in self.metric:
                score += dictionary[key]*self.metric[key]
            else:
                score += dictionary[key]
        return score

    def send_rreq(self,dest):
        self.seq_no += 1
        seq_no = self.seq_no
        orig = self.node_id
        sender = self.node_id
        power = self.INF
        coor = self.coor
        dist = 0
        hop = 0        
        message = 'RREQ|%s|%s|%s|%s|%s,%s|%s|%s|%s|\r\n'%(seq_no,orig,sender,dest,*self.coor,hop,dist,power)
        for child in self.childs:
            self.send(self.childs[child],message)

    def process_rreq(self,message):
        '''Process an incoming RREQ message'''
        # Extract the relevant parameters from the message
        seq_no = int(message[1])
        orig = message[2]
        sender = message[3]
        dest = message[4]
        coor = message[5].split(',')
        hop = int(message[6]) + 1
        dist = float(message[7])+self.distance(coor)
        power = min(float(message[8]),self.rem_power)
        # Cancel previous time
        if self.node_id == dest:
            if orig in self.timers:
                self.timers[orig].cancel()
        # Check if we are the origin. If we are, discard this RREP.
        if (self.node_id == orig):
            return
        # Calculate score
        score = self.obj_func({'dist':dist,'power':power,'hop':hop})
        # Insert or update routing table if needed
        if orig not in self.routing_table:
            self.routing_table[orig] = {
                'Next-Hop': sender,
                'Seq-No': seq_no,
                'Hop': hop,
                'Distance': dist,
                'Power': power,
                'Score': score,
                'Status': 1
            }
        elif self.routing_table[orig]['Seq-No'] < seq_no:
            # Update current path
            self.routing_table[orig] = {
                'Next-Hop': sender,
                'Seq-No': seq_no,
                'Hop': hop,
                'Distance': dist,
                'Power': power,
                'Score': score,
                'Status': 1
            }
        elif self.routing_table[orig]['Score'] < score:
            # Update routing table
            self.routing_table[orig] = {
                'Next-Hop':sender,
                'Seq-No': seq_no,
                'Hop':hop,
                'Distance': dist,
                'Power': power,
                'Score': score,
                'Status': 1
            }
        else:
            if self.node_id == dest:
                # Start or restart timer on getiing rreq
                self.timers[orig] = threading.Timer(self.BEST_PATH_WAIT_TIME,self.send_rrep,[orig,])
                self.timers[orig].start()
            return
        if self.node_id == dest:
            # Start or restart timer on getiing rreq
            self.timers[orig] = threading.Timer(self.BEST_PATH_WAIT_TIME,self.send_rrep,[orig,])
            self.timers[orig].start()
        else:
            self.forward_rreq(message)

    def forward_rreq(self,message):
        '''Rebroadcast an RREQ request (Called when RREQ is received by an intermediate node)'''
        coor = message[5].split(',')
        message[3] = self.node_id
        message[5] = '%s,%s'%tuple(self.coor)
        message[6] = str(int(message[6]) + 1)
        message[7] = str(float(message[7])+self.distance(coor))
        message[8] = str(min(float(message[8]),self.rem_power))
        message = '|'.join(message)
        for conn in self.childs.values():
            self.send(conn,message)

    def send_rrep(self,dest):
        '''Send an RREP message back to the RREQ originator'''
        self.seq_no += 1
        seq_no = self.seq_no
        orig = self.node_id
        sender = self.node_id
        power = self.INF
        coor = self.coor
        dist = 0
        hop = 0
        message = 'RREP|%s|%s|%s|%s|%s,%s|%s|%s|%s|\r\n'%(seq_no,orig,sender,dest,*coor,hop,dist,power)
        next_hop = self.routing_table[dest]['Next-Hop']
        self.send(self.parents[next_hop],message)

    def process_rrep(self,message):
        '''Process an incoming RREP message'''
        # Extract the relevant fields from the message
        seq_no = int(message[1])
        orig = message[2]
        sender = message[3]
        dest = message[4]
        coor = message[5].split(',')
        hop = int(message[6]) + 1
        dist = float(message[7])+self.distance(coor)
        power = min(float(message[8]),self.rem_power)

        score = self.obj_func({'dist':dist,'power':power,'hop':hop})
        if orig in self.routing_table:
            if self.routing_table[orig]['Seq-No'] > seq_no:
                return

        self.routing_table[orig] = {
            'Next-Hop':sender,
            'Seq-No': seq_no,
            'Hop':hop,
            'Distance': dist,
            'Power': power,
            'Score': score,
            'Status': 1
        }
        if self.node_id != dest:
            self.forward_rrep(message)

    def forward_rrep(self,message):
        dest = message[4]
        coor = message[5].split(',')
        message[3] = self.node_id
        message[5] = '%s,%s'%tuple(self.coor)
        message[6] = str(int(message[6]) + 1)
        message[7] = str(float(message[7])+self.distance(coor))
        message[8] = str(min(float(message[8]),self.rem_power))
        message = '|'.join(message)
        next_hop = self.routing_table[dest]['Next-Hop']
        self.send(self.parents[next_hop],message)

    def send_user_message(self,dest,msg_data):
        '''Send an USER message'''
        message = 'USER|%s|%s|%s|\r\n'%(self.node_id,dest,msg_data)
        # Reset routing table status to 0
        if dest in self.routing_table:
            self.routing_table[dest]['Status'] = 0
        self.send_rreq(dest)
        for _ in range(self.MAX_ATTEMPT):
            if dest in self.routing_table:
                if self.routing_table[dest]['Status']:
                    next_hop = self.routing_table[dest]['Next-Hop']
                    self.send(self.childs[next_hop],message)
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
                if dest in self.routing_table:
                    msg = self.pending_msg_q[dest].pop(0)
                    orig = msg['orig']
                    msg_data = msg['msg_data']
                    message = 'USER|%s|%s|%s|\r\n'%(orig,dest,msg_data)
                    next_hop = self.routing_table[dest]['Next-Hop']
                    self.send(self.childs[next_hop],message)
                else:
                    return
            self.pending_msg_q.pop(dest)

    def process_user_message(self,message):
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
            self.forward_user_message(message)

    def forward_user_message(self,message):
        '''Resend an USER message'''
        orig = message[1]
        dest = message[2]
        msg_data = message[3]
        message = '|'.join(message)
        if dest in self.routing_table:
            next_hop = self.routing_table[dest]['Next-Hop']
            self.send(self.childs[next_hop],message)
        else:
            if dest not in self.pending_msg_q:
                self.pending_msg_q[dest] = []
            self.pending_msg_q[dest].append({'orig':orig,'msg_data':msg_data})

    def child_handler(self,child):
        try:
            self.listener(self.childs[child])
        except:
            for table in list(self.routing_table):
                if self.routing_table[table]['Next-Hop'] == child:
                    self.routing_table.pop(table,None)

    def run(self):
        while True:
            try:
                conn , _ = self.sock.accept()
                node_id = conn.recv(21).decode()
                self.childs[node_id] = conn
                threading.Thread(target=self.child_handler,args=(node_id,)).start()
            except:
                print('Connection closed')
                break

class Node(AODV):
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
            self.nodes[node].metric = {'dist':-0.01,'hop': -1+factor,'power':factor}
            self.nodes[node].seq_no = 0
            self.nodes[node].rem_power = self.nodes[node].init_power
            self.nodes[node].sent_bytes = 0
            self.nodes[node].received_bytes = 0
            self.nodes[node].routing_table = {}
            self.nodes[node].timers = {}
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

    def plt_dest_connection(self,dest):
        self.init_neighbour()
        for node in self.nodes.values():
            if dest in node.routing_table:
                node.routing_table[dest]['Status'] = 0
        for node in self.nodes.values():
            if node.node_id != dest:
                node.send_rreq(dest)
                for _ in range(self.MAX_ATTEMPT):
                    if dest in node.routing_table:
                        if node.routing_table[dest]['Status']:
                            route = node.routing_table[dest]
                            x = [self.nodes[route['Next-Hop']].coor[0],node.coor[0]]
                            y = [self.nodes[route['Next-Hop']].coor[1],node.coor[1]]
                            plt.plot(x, y, '-o')
                            break
                    time.sleep(self.ATTEMPT_WAIT_TIME)

    def plot_neighbour_connection(self):
        for node in self.nodes:
            for child in self.nodes[node].childs:
                x = [self.nodes[node].coor[0],self.nodes[child].coor[0]]
                y = [self.nodes[node].coor[1],self.nodes[child].coor[1]]
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
            c.append(node.rem_power/node.init_power)
            s.append(3.14*25**2) # mult 8.1
            plt.text(x[-1], y[-1],node.node_id,size=20,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6,picker=True)
        plt.grid(True)

    def start_session(self,dest,no=1):
        count = 0
        while count != no or no != -1:
            for node in self.nodes:
                if node != dest:
                    sent = False
                    self.init_neighbour()
                    self.nodes[node].send_user_message(dest,'PING')
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
        y = np.arange(0.0,1.1, 0.1)
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

    def plot_msg_delivery_stat(self,dest,no=1):
        x = np.arange(0.0,1.2, 0.2)
        y = np.arange(1,self.no_of_node+1,1)
        y, x = np.meshgrid(y,x)
        z = np.zeros_like(y)
        for i,factor in enumerate(x[:,0]):
            print('%s%s%s'%('-'*18,round(factor,1),'-'*18))
            self.reset(factor)
            self.start_session(dest,no)
            for j,node in enumerate(self.nodes.values()):
                z[i][j] = node.sent_bytes+node.received_bytes
        x,y,z = x.ravel(),y.ravel(),z.ravel()
        b = np.zeros_like(z)
        c = list(map(lambda z:plt.cm.RdYlGn(z),z/z.max()))
        fig = plt.figure(figsize=(30,15),dpi=200)
        ax = fig.gca(projection='3d')
        ax.bar3d(x,y, b, 0, 0.05, z, shade=True,color=c, alpha=0.8)
        ax.set_zlabel('Data Transfer(Bytes)')
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('Node')
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
network.plot_msg_delivery_stat('127.0.0.1:8029',3)
network.nodes['127.0.0.1:8029'].msg_box