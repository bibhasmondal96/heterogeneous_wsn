import time
import socket
import threading

class RPL(threading.Thread):

    transfer_loss = {"send":0.005,"receive":0.002}
    transfer_threshold = {"send": 1.5, "receive": 0.5}
    metric = {'dist':-0.01,'rank': -1.0,'power':0.0}
    INF = 999
    MAX_ATTEMPT = 100
    ATTEMPT_WAIT_TIME = 0.2
    BEST_PATH_WAIT_TIME = 3

    def __init__(self,addr,coor,power,print_func):
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(addr)
        self.print = print_func

    def add_parent(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            self.parents['%s:%s'%node] = node

    def remove_parent(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            self.parents.pop('%s:%s'%node,None)
            self.best_parent.pop('%s:%s'%node,None)

    def add_child(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            self.childs['%s:%s'%node] = node

    def remove_child(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            self.childs.pop('%s:%s'%node,None)

    def max_byte(self,operation):
        avail_pow = self.rem_power-self.transfer_threshold[operation]
        byte = avail_pow/self.transfer_loss[operation]
        return int(byte)

    def power_loss(self,message,op):
        loss = len(message)*self.transfer_loss[op]
        return loss

    def listener(self,sock):
        while True:
            message,_ = sock.recvfrom(1024)
            if message:
                message = message.decode()
                if message[:4] == 'USER':
                    if len(message)<=self.max_byte('receive'):
                        # Update params
                        self.received_bytes += len(message)
                        self.rem_power -= self.power_loss(message,'receive')
                        self.on_recv(message)
                    else:
                        self.print('Low power\n')
                else:
                    self.on_recv(message)

    def on_recv(self,message):
        message = message.split('|')
        # Process message
        switch = {
            'DIS':self.process_dis,
            'DIO':self.process_dio,
            'USER': self.process_msg
        }
        switch[message[0]](message)

    def send(self,addr,message):
        if message[:4] != 'USER':
            # send message
            self.sock.sendto(message.encode(),addr)
        else:
            if len(message)<=self.max_byte('send'):
                # send message
                self.sock.sendto(message.encode(),addr)
                # Update params
                self.sent_bytes += len(message)
                self.rem_power -= self.power_loss(message,'send')
            else:
                self.print('Low power\n')

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
                'dag_id': dag_id,
                'node_id': sender,
                'score': score,
                'power': power,
                'is_best': 0
            }
        elif self.best_parent[orig]['dag_id'] < dag_id:
            # Update best parent for current dag
            self.best_parent[orig] = {
                'dag_id': dag_id,
                'node_id': sender,
                'score': score,
                'power': power,
                'is_best': 0
            }
        elif self.best_parent[orig]['score'] < score:
            # Update best parent
            self.best_parent[orig] = {
                'dag_id': dag_id,
                'node_id': sender,
                'score': score,
                'power': power,
                'is_best': 0
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
                    self.print('Hop: %s, Path power: %s, Node power: %s\n'%(self.rank,self.best_parent[dest]['power'],self.rem_power))
                    self.print(self.node_id+'->')
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
            self.print(self.node_id+'\n')
            self.print('New message arrived from %s\n'%orig)
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
            self.print(self.node_id+'->')
            self.send(self.parents[best_parent],message)
        else:
            if dest not in self.pending_msg_q:
                self.pending_msg_q[dest] = []
            self.pending_msg_q[dest].append({'orig':orig,'msg_data':msg_data})

    def run(self):
        try:
            self.listener(self.sock)
        except Exception as e:
            print('Connection closed')