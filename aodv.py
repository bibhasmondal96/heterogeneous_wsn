import time
import socket
import threading

class AODV(threading.Thread):

    transfer_loss = {"send":0.005,"receive":0.002}
    transfer_threshold = {"send": 1.0, "receive": 0.5}
    metric = {'dist':-0.01,'hop': -1.0,'power':0.0}
    INF = 999
    MAX_ATTEMPT = 100
    BEST_PATH_WAIT_TIME = 3
    ATTEMPT_WAIT_TIME = 0.2

    def __init__(self,addr,coor,power,print_func):
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
            for table in list(self.routing_table):
                if self.routing_table[table]['Next-Hop'] == node:
                    self.routing_table.pop(table,None)

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
            for table in list(self.routing_table):
                if self.routing_table[table]['Next-Hop'] == node:
                    self.routing_table.pop(table,None)

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
            'RREQ':self.process_rreq,
            'RREP':self.process_rrep,
            'USER': self.process_user_message
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
                    route = self.routing_table[dest]
                    next_hop = route['Next-Hop']
                    self.print('Hop: %s, Path power: %s, Node power: %s\n'%(route['Hop'],route['Power'],self.rem_power))
                    self.print('Path: %s->'%self.node_id)
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
            self.print(self.node_id+'\n')
            self.print('New message arrived from %s\n'%orig)
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
            self.print(self.node_id+'->')
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
        try:
            self.listener(self.sock)
        except Exception as e:
            print('Connection closed')
