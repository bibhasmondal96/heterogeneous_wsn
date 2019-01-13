'''Heterogenetic calculation on Network'''
import matplotlib.pyplot as plt
import random
import math
import sys
import numpy as np
class Network:
    class Node:
        def __init__(self, name,dist_range=[1,50]):
            self.name = name
            self.position = [random.randint(*dist_range), random.randint(*dist_range)]#
            self.sent = 0
            self.received = 0
            self.power = 5
            self.range = 25
            self.threshold = {"send": 1.5, "receive": 0.5}
            self.loss = {"send":0.005,"receive":0.002}
    
    def __init__(self,no):
        self.travers = []
        self.path=[]
        self.dp = [[None for _ in range(no)] for _ in range(no)]
        self.INF = 2**16
        self.avgPowConsumedPerSeason = 0
        self.nodes = {}
        for i in range(no):
            self.nodes[i+1]=self.Node(i+1)

    def printMatrix(self, mat):
        for i in range(len(mat)):
            for j in range(len(mat[i])):
                print("%-5s" % mat[i][j], end='')
            print()
    
    def distance(self,src,dest):
        return math.sqrt((self.nodes[src].position[0]-self.nodes[dest].position[0])**2 + \
            (self.nodes[src].position[1]-self.nodes[dest].position[1])**2)
    
    def minDist(self, src, dest):
        self.travers.append(src)
        if self.dp[src-1][dest-1] is not None:
            return self.dp[src-1][dest-1] # -1 because node indexing start from 1
        else:
            dist = self.distance(src,dest)

            if dist > self.nodes[src].range:
                dist=self.INF
            elif not self.path:
                self.path=[src,dest]

            for node in self.nodes.values():
                if node.name not in self.travers and node.name != dest and self.distance(src, node.name) <= self.nodes[src].range:
                    distan = self.distance(src, node.name) + self.minDist(node.name, dest)
                    if distan < dist:
                        self.travers.append(dest)
                        self.path = self.travers.copy()
                        self.travers.pop()  # for last dest
                        self.travers.pop()  # for continue check next node go get actual min distance
                        dist = distan
                    else:
                        # print(self.travers)
                        self.travers.pop() # one by one pop of insered element upto proper position
            self.dp[src-1][dest-1] = dist # memorization
            return dist

    def packetTransfer(self, src, dest, no):
        ''' First receive one packet and then send it to destination'''
        source = self.nodes[src]
        maxSent = int((source.power - source.threshold["send"])/source.loss["send"])
        maxSent = no if maxSent > no else  maxSent
        sourcePowerConsumed = source.loss["send"]*maxSent
        source.power -= sourcePowerConsumed
        # source.range -= int(source.loss["send"]*maxSent)**2   #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        source.range = round(source.power**2)
        source.sent+=maxSent
        destination = self.nodes[dest]
        totalThreshold = destination.threshold["receive"] + destination.threshold["send"]
        totalLoss = destination.loss["receive"]+destination.loss["send"]
        maxRecv = int((destination.power - totalThreshold)/totalLoss)
        maxRecv += int((destination.power-totalLoss*maxRecv)/destination.threshold["receive"])  # It recieve but can't send
        maxRecv = maxSent if maxRecv > maxSent else maxRecv
        destinationPowerConsumed = destination.loss["receive"]*maxRecv
        destination.power -= destinationPowerConsumed
        # destination.range -= int(destination.loss["receive"]*maxRecv)**2      #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        destination.range = round(destination.power**2)
        destination.received += maxRecv
        tottalPowerConsumed = sourcePowerConsumed + destinationPowerConsumed
        return maxRecv,tottalPowerConsumed

    def sentPacket(self,src,dest,no,delay=False):
        self.travers = []
        self.path = []
        self.dp = self.dp = [[None for _ in self.nodes] for _ in self.nodes] # for memorization
        dist = self.minDist(src,dest)   # Path will be calculate by this func
        if not self.path:
            no = 0
        totalPowerConsumed = 0
        for i in range(len(self.path)-1):
            sent,powerConsumed = self.packetTransfer(self.path[i], self.path[i+1], no)
            totalPowerConsumed += powerConsumed
            if no != sent:
                return False,averagePowerConsumed
            no=sent
        averagePowerConsumed = totalPowerConsumed/len(self.nodes)
        return True,averagePowerConsumed

    def startSeason(self,noOfPacket,destination):
        for node in self.nodes.keys():
            if node != destination:
                isAllReach,averagePowerConsumed = self.sentPacket(node, destination, noOfPacket)
                self.avgPowConsumedPerSeason = averagePowerConsumed/(len(self.nodes)-1) # -1 for ignoring destination->destination packet transfer
                if not isAllReach:
                    self.barPlot()
                    return

    def adjacencyMatrix(self):
        print("\nAdjacency Matrix:")
        adjMat = []
        for i in range(len(self.nodes)):
            adjMat.append([])
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    adjMat[i].append(1)
                else:
                    adjMat[i].append(0)
        self.printMatrix(adjMat)
        return adjMat

    def neighboursStatusStackPlot(self):
        red=[]
        green=[]
        for i in range(len(self.nodes)):
            r = []
            g = []
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    if self.nodes[j+1].power < 5*0.99:
                        r.append(self.nodes[j+1].name)
                    else:
                        g.append(self.nodes[j+1].name)
            if g:
                green.append(len(g)*100/len(r+g))
                plt.text(i,5,len(g),horizontalalignment='center',verticalalignment='center')
            else:
                green.append(0)
            if r:
                red.append(len(r)*100/len(r+g))
                plt.text(i,green[-1]+5,len(r),horizontalalignment='center',verticalalignment='center')
            else:
                red.append(0)
        plt.bar(range(len(self.nodes)),green,width = 0.75,color='g',label='Moderate Power')
        plt.bar(range(len(self.nodes)),red,width = 0.75,color='r',bottom=green,label='Low Power')
        plt.xticks(range(0,len(self.nodes)),range(1,len(self.nodes)+1))
        plt.yticks(range(0, 150, 10))
        plt.xlabel('Node no')
        plt.ylabel('Neighbours(%)')
        plt.gcf().canvas.set_window_title('Heterogenious Calculation')
        plt.title("Neighbour Status vs Nodes no", fontsize='large')
        plt.legend()
        plt.show()

    def neighboursStatusPlot(self):
        red=[]
        green=[]
        for i in range(len(self.nodes)):
            r = []
            g = []
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    if self.nodes[j+1].power < 5*0.99:
                        r.append(self.nodes[j+1].name)
                    else:
                        g.append(self.nodes[j+1].name)
            if g:
                green.append(len(g)*100/len(r+g))
                plt.text(i-0.20,5,len(g),horizontalalignment='center',verticalalignment='center')
            else:
                green.append(0)
            if r:
                red.append(len(r)*100/len(r+g))
                plt.text(i+0.20,5,len(r),horizontalalignment='center',verticalalignment='center')
            else:
                red.append(0)
        plt.bar(list(map(lambda x:x-0.20,range(len(self.nodes)))),green,width = 0.40,color='g',label='Moderate Power')
        plt.bar(list(map(lambda x:x+0.20,range(len(self.nodes)))),red,width = 0.40,color='r',label='Low Power')
        plt.xticks(range(0,len(self.nodes)),range(1,len(self.nodes)+1))
        plt.yticks(range(0, 150, 10))
        plt.xlabel('Node no')
        plt.ylabel('Neighbours(%)')
        plt.gcf().canvas.set_window_title('Heterogenious Calculation')
        plt.title("Neighbour Status vs Nodes no", fontsize='large')
        plt.legend()
        plt.show()

    def neighbourConnectionPlot(self):
        for i in range(len(self.nodes)):
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    x = [self.nodes[i+1].position[0],self.nodes[j+1].position[0]]
                    y = [self.nodes[i+1].position[1],self.nodes[j+1].position[1]]
                    plt.plot(x, y, '-o', color=plt.cm.prism(i))
                    
                
    def barPlot(self):
        x=[]
        y=[]
        color=[]
        for node in self.nodes.values():
            x.append(node.name)
            y.append(round((5-node.power)*100/5.0))
            color.append(plt.cm.Spectral(node.power/5.0))
            
        plt.bar(x,y,color=color,width = 2)
        plt.xlabel('Node')
        plt.ylabel('Energy Consumed(%)')
        plt.grid(True)
        plt.show()
        

    def scatterPlot(self):
        import matplotlib.patches as mpatches
        from matplotlib.collections import PatchCollection
        import numpy as np
        x=[]
        y=[]
        c=[]
        s=[]
        patches = []
        for node in self.nodes.values():
            x.append(node.position[0])
            y.append(node.position[1])
            c.append(node.power/5.0)
            s.append(3.14*25**2) # mult 8.1
            plt.text(x[-1], y[-1],node.name,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
            # patches.append(mpatches.Wedge((x[-1], y[-1]),node.range, 0, 360,label="hghjghjghjg",alpha=0.4,color = plt.cm.RdYlGn(node.power*1.1)))
            # plt.gca().add_patch(patches[-1])
        # p = PatchCollection(patches,alpha=0.4)
        # p.set_array(np.array(c))
        # plt.gca().add_collection(p)
        # plt.rcParams["figure.figsize"] = [15,15]
        plt.scatter(x, y, s=s, c=c, alpha=0.6)
        # self.neighbourConnectionPlot()
        # plt.gca().set_aspect("equal")
        # plt.xticks(range(-50, 150, 25))
        # plt.yticks(range(-50, 150, 25))
        plt.grid(True)
        plt.show()


    def bandPlot(self):
        x=[]
        y=[]
        color=[]
        s=[]
        for node in self.nodes.values():
            x.append(node.name)
            y.append(node.power)
            s.append(3.14*node.range**2)
            if node.power < 5.0*0.99: # 10% of initial energy
                color.append('red')
            else:
                color.append('green')
            plt.text(x[-1], y[-1],node.name,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))

        plt.axhline(y=5.0*0.99)
        plt.scatter(x, y, s=s, color=color,edgecolors='black',alpha=0.6)
        plt.xticks(x,x)
        plt.xlabel('Node no')
        plt.ylabel('Energy Remain(%)')
        plt.gcf().canvas.set_window_title('Heterogenious Calculation')
        plt.grid(True)
        plt.show()


if __name__ == "__main__":
    x = []
    y = []
    nets = []
    # for no in range(20,201,20):
    #     net = Network(no)
    #     net.startSeason(1,no)
    #     y.append(net.avgPowConsumedPerSeason)
    #     x.append(no)
    #     nets.append(net)
    #     # break
    net = Network(20)
    for _ in range(4):
        net.startSeason(1,20)
    # plt.plot(x,y)
    # plt.xlabel('Nodes')
    # plt.ylabel('Energy Consumed(%)')
    # plt.gcf().canvas.set_window_title('Heterogenious Calculation')
    # plt.title("Energy Consumed vs Nodes", fontsize='large')
    # plt.xticks(x,x)
    # plt.grid(True)
    # plt.show()
    # nets[0].scatterPlot()
    # nets[0].bandPlot()
    # nets[0].neighboursStatusStackPlot()
    net.neighboursStatusPlot()
