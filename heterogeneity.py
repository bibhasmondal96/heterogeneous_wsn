'''Heterogenetic calculation on Network'''
import random
import math
import sys
class Network:
    class Node:
        sample_position = [[[6, 5], [28, 23], [22, 22], [16, 10], [1, 10]], [[18, 28], [
            25, 5], [28, 10], [3, 1], [2, 15]], [[24, 8], [1, 19], [25, 19], [13, 20], [3, 30]], [[21, 25], [18, 12], [30, 21], [24, 19], [8, 6]]]
        def __init__(self, name,dist_range=[1,30]):
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
        if self.dp[src-1][dest-1]:
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

    def packetTransferDelay(self, src, dest, no):
        ''' First recieve max posible packet from source then send max possible packet to destination'''
        source = self.nodes[src]
        maxSent = int((source.power - source.threshold["send"])/source.loss["send"])
        maxSent = no if maxSent > no else  maxSent        
        source.power -= source.loss["send"]*maxSent
        # source.range -= int(source.loss["send"]*maxSent)**2   #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        source.range = round(source.power**2)
        source.sent+=maxSent
        destination = self.nodes[dest]
        maxRecv = int((destination.power - destination.threshold["receive"])/destination.loss["receive"])
        maxRecv = maxSent if maxRecv > maxSent else maxRecv
        destination.power -= destination.loss["receive"]*maxRecv
        # destination.range -= int(destination.loss["receive"]*maxRecv)**2      #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        destination.range = round(destination.power**2)
        destination.received += maxRecv
        return maxRecv

    def packetTransferInstant(self, src, dest, no):
        ''' First receive one packet and then send it to destination'''
        source = self.nodes[src]
        maxSent = int((source.power - source.threshold["send"])/source.loss["send"])
        maxSent = no if maxSent > no else  maxSent        
        source.power -= source.loss["send"]*maxSent
        # source.range -= int(source.loss["send"]*maxSent)**2   #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        source.range = round(source.power**2)
        source.sent+=maxSent
        destination = self.nodes[dest]
        totalThreshold = destination.threshold["receive"] + destination.threshold["send"]
        totalLoss = destination.loss["receive"]+destination.loss["send"]
        maxRecv = int((destination.power - totalThreshold)/totalLoss)
        maxRecv += int((destination.power-totalLoss*maxRecv)/destination.threshold["receive"])  # It recieve but can't send
        maxRecv = maxSent if maxRecv > maxSent else maxRecv
        destination.power -= destination.loss["receive"]*maxRecv
        # destination.range -= int(destination.loss["receive"]*maxRecv)**2      #This will not work because the energy loss for small no of packet is tends to 0. so range does no decreases.
        destination.range = round(destination.power**2)
        destination.received += maxRecv
        return maxRecv

    def sentPacket(self,src,dest,no,delay=False):
        # sys.stdout = open("Heterogen.txt","a")
        print("-"*100)
        self.travers = []
        self.path = []
        self.dp = self.dp = [[None for _ in self.nodes] for _ in self.nodes] # for memorization
        dist = self.minDist(src,dest)   # Path will be calculate by this func 
        print("Sending Packet from Node(%s): %s\n"%(src,no))
        print("Shortest Distance: %s\n"% dist if dist!=self.INF else "Infinite")
        print("Shortest Path: %s\n" % self.path)
        if not self.path:
            no = 0
        for i in range(len(self.path)-1):
            if delay:
                sent = self.packetTransferDelay(self.path[i], self.path[i+1], no)
            else:
                sent = self.packetTransferInstant(self.path[i], self.path[i+1], no)
            self.showState(self.path[i], self.path[i+1])
            print("Packet loss from Node(%s) to Node(%s): %s" % (self.path[i], self.path[i+1],no-sent))
            print("-"*67)
            no=sent
        print("Packet Recieved at Node(%s): %s\n" % (dest,no))
        print("-"*100)
        # sys.stdout.close()

    def showState(self,src,dest):
        source = self.nodes[src]
        destination = self.nodes[dest]
        print("-"*67)
        print("%-50s%s" % ("Node(%s)"%src, "Node(%s)"%dest))
        print("-"*67)
        print("%-50s%s" % ("Position: %s"%source.position, "Position: %s"%destination.position))
        print("%-50s%s" % ("Sent: %s" % source.sent, "Sent: %s"%destination.sent))
        print("%-50s%s" % ("Recieve: %s"%source.received, "Recieve: %s"%destination.received))
        print("%-50s%s" % ("Power: %s"%source.power, "Power: %s"%destination.power))
        print("%-50s%s\n" % ("Range: %s"%source.range, "Range: %s"%destination.range))

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


if __name__ == "__main__":
    net = Network(50)
    net.sentPacket(1, 5, 2)
    net.sentPacket(2, 5, 500)
    net.sentPacket(3, 5, 6)
    net.sentPacket(4, 5, 15)
