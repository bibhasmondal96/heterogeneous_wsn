import time
import numpy as np
from node import Node
import matplotlib.pyplot as plt

class Network:

    MAX_ATTEMPT = 100
    ATTEMPT_WAIT_TIME = 0.2

    def __init__(self,no_of_node=30,initial_node_power=50,dist_range=[0,50],ip='127.0.0.1',start_port=8000,print_func=print):
        self.no_of_node = no_of_node
        self.print = print_func
        self.nodes = {}
        for i in range(no_of_node):
            addr = (ip,start_port+i)
            self.nodes['%s:%s'%addr] = Node(addr,initial_node_power,dist_range,print_func)
            self.nodes['%s:%s'%addr].start()
        self.set_dest(addr)
        # Initilize neighbour
        self.init_neighbour()

    def set_dest(self,addr):
        self.dest = '%s:%s'%addr
        self.death_state = {0.0:[],0.2:[],0.4:[],0.6:[],0.8:[],1.0:[]}
        self.max_state = {0.0:[],0.2:[],0.4:[],0.6:[],0.8:[],1.0:[]}
        # state = self.__dict__.copy()
        # state.pop('max_state')
        # state.pop('death_state')
        # for i in list(self.max_state):
        #     self.max_state[i].append(state)
        #     self.death_state[i].append(state)

    def init_neighbour(self):
        for node1 in self.nodes:
            for node2 in self.nodes:
                if node1 != node2:
                    if self.nodes[node1].is_neighbour(self.nodes[node2].coor):
                        if node1 not in self.nodes[node2].parents:
                            self.nodes[node2].add_parent(self.nodes[node1].addr)
                        if node2 not in self.nodes[node1].childs:
                            self.nodes[node1].add_child(self.nodes[node2].addr)
                    else:
                        # Remove from childs and close conn
                        if node1 in self.nodes[node2].parents:
                            self.nodes[node2].remove_parent(self.nodes[node1].addr)
                        if node2 in self.nodes[node1].childs:
                            self.nodes[node1].remove_child(self.nodes[node2].addr)

    def shutdown(self):
        for node in self.nodes:
            self.nodes[node].sock.close()

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

    def start_session(self,no=1,save_state=False):
        count = 0
        while count != no or no==-1: # -1 for infinite
            for node in self.nodes:
                if node != self.dest:
                    sent = False
                    self.init_neighbour()
                    self.nodes[node].send_msg(self.dest,'PING')
                    # Check whether msg reaches to dest
                    for _ in range(self.MAX_ATTEMPT):
                        if node in self.nodes[self.dest].msg_box:
                            if not self.nodes[self.dest].msg_box[node][-1]['is_read']:
                                self.nodes[self.dest].msg_box[node][-1]['is_read'] = 1
                                sent = True
                                break
                        time.sleep(self.ATTEMPT_WAIT_TIME)
                    if save_state:
                        state = self.__dict__.copy()
                        state.pop('max_state')
                        state.pop('death_state')
                        self.death_state[self.nodes[self.dest].metric['power']].append(state)
                    if not sent: return count
            count += 1
            self.print('No of session completed: %s\n'%count)
            if save_state:
                state = self.__dict__.copy()
                state.pop('max_state')
                state.pop('death_state')
                self.max_state[self.nodes[self.dest].metric['power']].append(state)
        return count

    def first_death(self):
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            self.print('%s%s%s\n'%('-'*18,i,'-'*18))
            self.reset(i)
            self.start_session(-1,True)

    def gini_coefficient(self,nodes):
        x = []
        y = []
        for i,node1 in enumerate(nodes):
            neighbours_power = []
            for node2 in nodes:
                if node1 != node2:
                    if nodes[node1].is_neighbour(nodes[node2].coor):
                        neighbours_power.append(nodes[node2].rem_power)
            y.append(sum(neighbours_power))
            x.append((i+1)/len(nodes))
        y.sort()
        b = y.copy()
        n = len(nodes)
        T = sum(y)
        x = [0]+x
        y = [0]+[sum(y[:i])/T for i in range(1,len(y)+1)]
        # Caluclating gini coeff
        polygon_area = (1/(n*T))*sum([(n-i+1/2)*b[i-1] for i in range(1,n+1)])
        gini_coefficient = 1-2*polygon_area
        return gini_coefficient

    def plt_network(self,ax):
        x=[]
        y=[]
        c=[]
        s=[]
        for node in self.nodes.values():
            x.append(node.coor[0])
            y.append(node.coor[1])
            c.append(node.rem_power/node.init_power)
            s.append(3.14*25**2) # mult 8.1
            ax.text(x[-1], y[-1],node.node_id,size=20,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        ax.scatter(x, y, s=s, c=c, alpha=0.6,picker=True)
        ax.grid(True)

    def plt_node_neighbour(self,plt,node_index):
        nodes = list(self.nodes.values())
        x=[nodes[node_index].coor[0]]
        y=[nodes[node_index].coor[1]]
        c=[nodes[node_index].rem_power/nodes[node_index].init_power]
        s=[3.14*25**2]
        plt.text(x[-1], y[-1],nodes[node_index].node_id,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        for i,node in enumerate(nodes):
            if i != node_index:
                if nodes[node_index].is_neighbour(node.coor):
                    x.append(node.coor[0])
                    y.append(node.coor[1])
                    c.append(node.rem_power/node.init_power)
                    s.append(3.14*25**2) # mult 8.1
                    _x = [nodes[node_index].coor[0],node.coor[0]]
                    _y = [nodes[node_index].coor[1],node.coor[1]]
                    plt.plot(_x, _y, '-o')
                    plt.text(x[-1], y[-1],node.node_id,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6)
        plt.grid(True)

    def plt_neighbours_connection(self,ax):
        self.plt_network(ax)
        for node in self.nodes:
            for child in self.nodes[node].childs:
                x = [self.nodes[node].coor[0],self.nodes[child].coor[0]]
                y = [self.nodes[node].coor[1],self.nodes[child].coor[1]]
                ax.plot(x, y, '-o')

    def plt_dest_connection(self,ax):
        self.plt_network(ax)
        self.init_neighbour()
        for node in self.nodes.values():
            if self.dest in node.best_parent:
                node.best_parent[self.dest]['is_best'] = 0
        self.nodes[self.dest].send_dio()
        for node in self.nodes.values():
            for _ in range(self.MAX_ATTEMPT):
                if self.dest in node.best_parent:
                    if node.best_parent[self.dest]['is_best']:
                        best_parent = self.nodes[node.best_parent[self.dest]['node_id']]
                        x = [best_parent.coor[0],node.coor[0]]
                        y = [best_parent.coor[1],node.coor[1]]
                        ax.plot(x, y, '-o')
                        break
                time.sleep(self.ATTEMPT_WAIT_TIME)

    def plt_lorentz_curve(self,ax):
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
        ax.plot(x,y,label="Lorenz curve")
        # Line of perfect equality
        ax.plot([x[0],x[-1]],[y[0],y[-1]],label="Line of perfect equality")
        # Line of perfect inequality
        ax.plot([x[0],x[-1],x[-1]],[y[0],y[0],y[-1]],color='black',label="Line of perfect inequality")
        ax.text(0.2, 0.7,"Gini coefficient: %s"%round(gini_coefficient,2),horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        ax.set_xlabel('Nodes(%)')
        ax.set_ylabel('Energy(%)')
        ticks = list(map(lambda v:v/100,range(0,101,10)))
        ax.set_title("Energy(%) vs Nodes(%)", fontsize='large')
        ax.set_xticks(ticks,ticks)
        ax.set_yticks(ticks,ticks)
        ax.grid(True)
        ax.legend()

    def plt_max_session(self,ax):
        max_session = []
        power_factor = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            max_session.append(len(self.max_state[i]))
            power_factor.append(i)
        ax.plot(power_factor,max_session)
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('No of session')
        ax.set_title("Max no of session vs Power Factor", fontsize='large')
        ax.grid(True)

    def plt_gini_stat(self,ax,state = 'max_state'):
        gini_index = []
        power_factor = []
        for i in [0.0,0.2,0.4,0.6,0.8,1.0]:
            nodes = getattr(self,state)[i][-1]['nodes']
            gini_index.append(self.gini_coefficient(nodes))
            power_factor.append(i)
        ax.plot(power_factor,gini_index)
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('Gini Coefficient')
        ax.set_title("Gini Coefficient vs Power Factor", fontsize='large')

    def plt_energy_stat(self,ax,state='max_state'):
        x = np.arange(0.0,1.2, 0.2)
        y = np.arange(0.1,1.0, 0.1)
        y, x = np.meshgrid(y,x)
        z = np.zeros_like(y)
        for i,factor in enumerate(x[:,0]):
            for node in getattr(self,state)[round(factor,1)][-1]['nodes'].values():
                for j,percent in enumerate(y[0]):
                    if percent-0.1 < node.rem_power/node.init_power <= percent:
                        z[i][j] += 1
        x,y,z = x.ravel(),y.ravel(),z.ravel()
        b = np.zeros_like(z)
        c = list(map(lambda y:plt.cm.RdYlGn(y),y))
        ax.bar3d(x,y, b, 0.01,0.5 , z, shade=True,color=c, alpha=0.8)
        ax.set_zlabel('No of nodes')
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('Remaining Energy')
        ax.set_title('Energy status at %s'%state)
        ax.grid(True)

    def plt_msg_delivery_stat(self,ax,state='max_state'):
        x = np.arange(0.0,1.2, 0.2)
        y = np.arange(1,self.no_of_node+1,1)
        y, x = np.meshgrid(y,x)
        z = np.zeros_like(y)
        for i,factor in enumerate(x[:,0]):
            for j,node in enumerate(getattr(self,state)[round(factor,1)][-1]['nodes'].values()):
                z[i][j] = node.sent_bytes+node.received_bytes
        x,y,z = x.ravel(),y.ravel(),z.ravel()
        b = np.zeros_like(z)
        c = list(map(lambda z:plt.cm.RdYlGn(z),z/z.max()))
        ax.bar3d(x,y, b, 2,0.1, z, shade=True,color=c, alpha=0.8)
        ax.set_zlabel('Data Transfer(Bytes)')
        ax.set_xlabel('Power Factor')
        ax.set_ylabel('Node')
        ax.set_title('Msg delivary status at %s'%state)
        ax.grid(True)
