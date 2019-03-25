import random
import math

class Network:
    class Node:
        def __init__(self, name,dist_range=[1,50],power=5):
            self.name = name
            self.position = [random.randint(*dist_range), random.randint(*dist_range)]
            self.sent = 0
            self.received = 0
            self.power = power
            self.range = power**2
            self.transferThreshold = {"send": 1.5, "receive": 0.5}
            self.transferLoss = {"send":0.005,"receive":0.002}


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
        maxSent = int((source.power - source.transferThreshold["send"])/source.transferLoss["send"])
        maxSent = no if maxSent > no else  maxSent
        sourcePowerConsumed = source.transferLoss["send"]*maxSent
        source.power -= sourcePowerConsumed
        # source.range -= int(source.transferLoss["send"]*maxSent)**2   #This will not work because the energy transferLoss for small no of packet is tends to 0. so range does no decreases.
        source.range = round(source.power**2)
        source.sent+=maxSent
        destination = self.nodes[dest]
        totalThreshold = destination.transferThreshold["receive"] + destination.transferThreshold["send"]
        totalLoss = destination.transferLoss["receive"]+destination.transferLoss["send"]
        maxRecv = int((destination.power - totalThreshold)/totalLoss)
        maxRecv += int((destination.power-totalLoss*maxRecv)/destination.transferThreshold["receive"])  # It recieve but can't send
        maxRecv = maxSent if maxRecv > maxSent else maxRecv
        destinationPowerConsumed = destination.transferLoss["receive"]*maxRecv
        destination.power -= destinationPowerConsumed
        # destination.range -= int(destination.transferLoss["receive"]*maxRecv)**2      #This will not work because the energy transferLoss for small no of packet is tends to 0. so range does no decreases.
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
                return False,totalPowerConsumed/len(self.nodes)
            no=sent
        averagePowerConsumed = totalPowerConsumed/len(self.nodes)
        return True,averagePowerConsumed


    def startSeason(self,noOfPacket,destination):
        for node in self.nodes.keys():
            if node != destination:
                isAllReach,averagePowerConsumed = self.sentPacket(node, destination, noOfPacket)
                self.avgPowConsumedPerSeason = averagePowerConsumed/(len(self.nodes)-1) # -1 for ignoring destination->destination packet transfer
                if not isAllReach:
                    # self.barPlot()
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


    def neighboursStatusStackPlot(self,plt):
        red=[]
        green=[]
        for i in range(len(self.nodes)):
            r = []
            g = []
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    if self.nodes[j+1].power < 5*0.1: #10% of initial Energy
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
                plt.text(i,97,len(r),horizontalalignment='center',verticalalignment='center')
            else:
                red.append(0)
        plt.bar(range(len(self.nodes)),green,width = 0.75,color='g',label='Moderate Power')
        plt.bar(range(len(self.nodes)),red,width = 0.75,color='r',bottom=green,label='Low Power')
        plt.set_xticks(range(0,len(self.nodes)),range(1,len(self.nodes)+1))
        plt.set_yticks(range(0, 150, 10))
        plt.set_xlabel('Node no')
        plt.set_ylabel('Neighbours(%)')
        plt.set_title("Neighbour Status vs Nodes no", fontsize='large')
        plt.legend()


    def neighboursStatusPlot(self,plt):
        red=[]
        green=[]
        for i in range(len(self.nodes)):
            r = []
            g = []
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    if self.nodes[j+1].power < 5*0.1: #10% of initial Energy
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
        plt.set_xticks(range(0,len(self.nodes)),range(1,len(self.nodes)+1))
        plt.set_yticks(range(0, 150, 10))
        plt.set_xlabel('Node no')
        plt.set_ylabel('Neighbours(%)')
        plt.set_title("Neighbour Status vs Nodes no", fontsize='large')
        plt.legend()


    def neighbourConnectionPlot(self,plt):
        for i in range(len(self.nodes)):
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    x = [self.nodes[i+1].position[0],self.nodes[j+1].position[0]]
                    y = [self.nodes[i+1].position[1],self.nodes[j+1].position[1]]
                    plt.plot(x, y, '-o')


    def lorentzCurve(self,plt):
        x = []
        y = []
        for i in range(len(self.nodes)):
            neighboursPower = []
            for j in range(len(self.nodes)):
                if self.distance(i+1,j+1)<=self.nodes[i+1].range and i!=j:
                    neighboursPower.append(self.nodes[j+1].power)
            y.append(sum(neighboursPower))
            x.append((i+1)/len(self.nodes))
        y.sort()
        b = y.copy()
        n = len(self.nodes)
        T = sum(y)
        x = [0]+x
        y = [0]+[sum(y[:i])/T for i in range(1,len(y)+1)]
        # Caluclating gini coeff
        polygonArea = (1/(n*T))*sum([(n-i+1/2)*b[i-1] for i in range(1,n+1)])
        giniCoefficient = 1-2*polygonArea
        # Lorenz curve
        plt.plot(x,y,label="Lorenz curve")
        # Line of perfect equality
        plt.plot([x[0],x[-1]],[y[0],y[-1]],label="Line of perfect equality")
        # Line of perfect inequality
        plt.plot([x[0],x[-1],x[-1]],[y[0],y[0],y[-1]],color='black',label="Line of perfect inequality")
        plt.text(0.2, 0.7,"Gini coefficient: %s"%round(giniCoefficient,2),horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.set_xlabel('Nodes(%)')
        plt.set_ylabel('Energy(%)')
        ticks = list(map(lambda v:v/100,range(0,101,10)))
        plt.set_title("Energy(%) vs Nodes(%)", fontsize='large')
        plt.set_xticks(ticks,ticks)
        plt.set_yticks(ticks,ticks)
        plt.grid(True)
        plt.legend()

    def scatterPlot(self,plt):
        x=[]
        y=[]
        c=[]
        s=[]
        for node in self.nodes.values():
            x.append(node.position[0])
            y.append(node.position[1])
            c.append(node.power/5.0)
            s.append(3.14*25**2) # mult 8.1
            plt.text(x[-1], y[-1],node.name,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6,picker=True)
        # self.neighbourConnectionPlot()
        plt.grid(True)

    def neighbourPlot(self,plt,node):
        x=[self.nodes[node].position[0]]
        y=[self.nodes[node].position[1]]
        c=[self.nodes[node].power/5.0]
        s=[3.14*25**2]
        plt.text(x[-1], y[-1],self.nodes[node].name,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        for i in range(len(self.nodes)):
            if self.distance(node,i+1)<=self.nodes[node].range and i+1!=node:
                x.append(self.nodes[i+1].position[0])
                y.append(self.nodes[i+1].position[1])
                c.append(self.nodes[i+1].power/5.0)
                s.append(3.14*25**2) # mult 8.1
                _x = [self.nodes[node].position[0],self.nodes[i+1].position[0]]
                _y = [self.nodes[node].position[1],self.nodes[i+1].position[1]]
                plt.plot(_x, _y, '-o')
                plt.text(x[-1], y[-1],self.nodes[i+1].name,horizontalalignment='center',verticalalignment='center',bbox=dict(facecolor='red', alpha=0.4))
        plt.scatter(x, y, s=s, c=c, alpha=0.6)
        plt.grid(True)

    def bandPlot(self,plt):
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
        plt.set_xticks(x,x)
        plt.set_xlabel('Node no')
        plt.set_ylabel('Energy Remain(%)')
        plt.grid(True)
