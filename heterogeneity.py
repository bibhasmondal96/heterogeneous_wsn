'''Heterogenetic calculation on Network'''
import random
import math
import sys
import matplotlib.pyplot as plt

class Network:
    class Node:
        sample_position = [[[6, 5], [28, 23], [22, 22], [16, 10], [1, 10]], [[18, 28], [
            25, 5], [28, 10], [3, 1], [2, 15]], [[24, 8], [1, 19], [25, 19], [13, 20], [3, 30]], [[21, 25], [18, 12], [30, 21], [24, 19], [8, 6]]]

        def __init__(self, name, dist_range=[1, 30]):
            self.name = name
            # [random.randint(*dist_range), random.randint(*dist_range)]#
            self.position = [random.randint(*dist_range), random.randint(*dist_range)]
            self.sent = 0
            self.received = 0
            self.power = 5
            self.range = 25
            self.threshold = {"send": 1.5, "receive": 0.5}
            self.loss = {"send": 0.005, "receive": 0.002}

    def __init__(self, no):
        self.travers = []
        self.path = []
        self.INF = 2**16
        self.nodes = {}
        for i in range(no):
            self.nodes[i+1] = self.Node(i+1)

    def printMatrix(self, mat):
        for i in range(len(mat)):
            for j in range(len(mat[i])):
                print("%-5s" % mat[i][j], end='')
            print()

    def distance(self, src, dest):
        return math.sqrt((self.nodes[src].position[0]-self.nodes[dest].position[0])**2 +
                         (self.nodes[src].position[1]-self.nodes[dest].position[1])**2)

    def minDist(self, src, dest):
        self.travers.append(src)
        dist = self.distance(src, dest)

        if dist > self.nodes[src].range:
            dist = self.INF
        elif not self.path:
            self.path = [src, dest]

        for node in self.nodes.values():
            if node.name not in self.travers and node.name != dest and self.distance(src, node.name) <= self.nodes[src].range:
                distan = self.distance(src, node.name) + self.minDist(node.name, dest)
                if distan < dist:
                    self.travers.append(dest)
                    self.path = self.travers.copy()
                    print(self.path)
                    self.travers.pop()  # for last dest
                    self.travers.pop()  # for continue check next node go get actual min distance
                    dist = distan
                else:
                    self.travers.pop()  # one by one pop of insered element upto proper position
        return dist


    def packetTransferInstant(self, src, dest, no):
        ''' First receive one packet and then send it to destination'''
        source = self.nodes[src]
        maxSent = int((source.power - source.threshold["send"])/source.loss["send"])
        maxSent = no if maxSent > no else maxSent
        source.power -= source.loss["send"]*maxSent
        source.range = round(source.power**2)
        source.sent += maxSent
        destination = self.nodes[dest]
        totalThreshold = destination.threshold["receive"] + destination.threshold["send"]
        totalLoss = destination.loss["receive"]+destination.loss["send"]
        maxRecv = int((destination.power - totalThreshold) / totalLoss)
        maxRecv += int((destination.power-totalLoss*maxRecv) / destination.threshold["receive"])  # It recieve but can't send
        maxRecv = maxSent if maxRecv > maxSent else maxRecv
        destination.power -= destination.loss["receive"]*maxRecv
        destination.range = round(destination.power**2)
        destination.received += maxRecv
        return maxRecv

    def sentPacket(self, src, dest, no):
        for i in range(src,dest):
            sent = self.packetTransferInstant(i,i+1, no)
            if no != sent:
                return False
            no = sent
        return True


    def startSeason(self,noOfPacket,destination):
        while True:
            for node in self.nodes.keys():
                if node != destination:
                    if not self.sentPacket(node, destination, noOfPacket):
                        self.plot()
                        return

    def plot(self):
        x=[]
        y=[]
        for node in self.nodes.values():
            x.append(node.name)
            y.append(round((5-node.power)*100/5.0))
        plt.plot(x,y)
        plt.xlabel('Node')
        plt.ylabel('Energy(%)')
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    net = Network(50)
    net.startSeason(1,50)
    # net.sentPacket(1, 5, 1)
    # net.sentPacket(2, 5, 1)
    # net.sentPacket(3, 5, 1)
    # net.sentPacket(4, 5, 1)
