import socket
import logging
import threading
AODV_PATH_DISCOVERY_TIME = 30
AODV_ACTIVE_ROUTE_TIMEOUT = 30
class AODV(threading.Thread):
    seq_no = 0
    rreq_id = 0
    node_id = None
    sock = None
    neighbours = {}
    status = "Active"
    rreq_id_list = {}
    routing_table = {}

    def __init__(self,node_id):
        self.node_id = node_id

    def create_server_and_listen(self):
        self.sock = socket.socket()
        self.sock.bind(('0',0))
        self.sock.listen(5)
        while True:
            conn , _ = self.sock.accept()
            node_id = conn.recv(1024)
            self.neighbours[node_id] = conn

    def neighbour_of(self,nodes):
        if not isinstance(nodes,list):
            nodes = [nodes]
        for node in nodes:
            s = socket.socket()
            s.connect(node)

    def send_rreq(self,dest,dest_seq_no=-1):
        '''Broadcast an RREQ message for the given destination'''
        # Increment our sequence number
        self.seq_no = self.seq_no + 1
        # Increment the RREQ_ID
        self.rreq_id = self.rreq_id + 1
        # Construct the RREQ packet
        message_type = "RREQ_MESSAGE"
        sender = self.node_id
        hop_count = 0
        rreq_id = self.rreq_id
        orig = self.node_id
        orig_seq_no = self.seq_no
        message = message_type + ":" + sender + ":" + str(hop_count) + ":" + str(rreq_id) + ":" + str(dest) + ":" + str(dest_seq_no) + ":" + str(orig) + ":" + str(orig_seq_no)
        
        # Broadcast the RREQ packet to all the neighbors
        for conn in self.neighbours:
            conn.send(message)
            logging.debug("['" + message_type + "', 'Broadcasting RREQ to " + dest + "']")

    def restart_route_timer(self, route, create):
        '''Create / Restart the lifetime timer for the given route'''
        if (create == False):
            timer = route['Lifetime']
            timer.cancel()
        timer = threading.Timer(AODV_ACTIVE_ROUTE_TIMEOUT, self.route_timeout, [route])
        route['Lifetime'] = timer
        route['Status'] = 'Active'
        timer.start()

    def route_timeout(self, route):
        '''Handle route timeouts'''
        # Remove the route from the routing table
        key = route['Destination']
        self.routing_table.pop(key)
        # If the destination is a neighbor, remove it from the neighbor table as well
        if key in self.neighbours:
            self.neighbours.pop(key)
        logging.debug("aodv_process_route_timeout: removing " + key + " from the routing table.")

    def path_discovery_timeout(self, node, rreq_id):
        '''Handle Path Discovery timeouts'''
        # Remove the buffered RREQ_ID for the given node
        if node in self.rreq_id_list:
            if rreq_id is self.rreq_id_list[node]:
                self.rreq_id_list.pop(node)

    def process_rreq(self,message):
        '''Process an incoming RREQ message'''
        # Ignore the message if we are not active
        if (self.status == "Inactive"):
            return
        # Extract the relevant parameters from the message
        message_type = message[0]
        sender = message[1]
        hop_count = int(message[2]) + 1
        message[2] = str(hop_count)
        rreq_id = int(message[3])
        dest = message[4]
        # dest_seq_no = int(message[5])
        orig = message[6]
        orig_seq_no = int(message[7])
        logging.debug("['" + message_type + "', 'Received RREQ to " + dest + " from " + sender + "']")
        # Discard this RREQ if we have already received this before
        if orig in self.rreq_id_list:
            if rreq_id == self.rreq_id_list[orig]:
                logging.debug("['RREQ_MESSAGE', 'Ignoring duplicate RREQ (" + orig + ", " + str(rreq_id) + ") from " + sender + "']")
                return
        # This is a new RREQ message. Buffer it first
        self.rreq_id_list[orig] = rreq_id
        
        path_discovery_timer = threading.Timer(AODV_PATH_DISCOVERY_TIME,self.path_discovery_timeout, [orig, rreq_id])
        path_discovery_timer.start()
        '''
        Check if we have a route to the source. If we have, see if we need
        to update it. Specifically, update it only if:
        
        1. The destination sequence number for the route is less than the
        originator sequence number in the packet
        2. The sequence numbers are equal, but the hop_count in the packet
        + 1 is lesser than the one in routing table
        3. The sequence number in the routing table is unknown
        
        If we don't have a route for the originator, add an entry
        '''
        if orig in self.routing_table:
            route = self.routing_table[orig]
            if (int(route['Seq-No']) < orig_seq_no):
                route['Seq-No'] = orig_seq_no
                self.restart_route_timer(route, False)
            elif (int(route['Seq-No']) == orig_seq_no):
                if (int(route['Hop-Count']) > hop_count):
                    route['Hop-Count'] = hop_count
                    route['Next-Hop'] = sender
                    self.restart_route_timer(route, False)
            elif (int(route['Seq-No']) == -1):
                route['Seq-No'] = orig_seq_no
                self.restart_route_timer(route, False)
        else:
            self.routing_table[orig] = {'Destination': str(orig),
                                        'Next-Hop': str(sender),
                                        'Seq-No': str(orig_seq_no),
                                        'Hop-Count': str(hop_count),
                                        'Status': 'Active'}
            self.restart_route_timer(self.routing_table[orig], True)
        # Check if we are the destination. If we are, generate and send an RREP back.
        if (self.node_id == dest):
            self.send_rrep(orig, sender, dest, dest, 0, 0)
            return
        # We are not the destination. Check if we have a valid route
        # to the destination. If we have, generate and send back an
        # RREP.
        if dest in self.routing_table:
            # Verify that the route is valid and has a higher seq number
            route = self.routing_table[dest]
            status = route['Status']
            route_dest_seq_no = int(route['Seq-No'])
            if (status == "Active" and route_dest_seq_no >= dest_seq_no):
                self.send_rrep(orig, sender, self.node_id, dest, route_dest_seq_no, int(route['Hop-Count']))
                return
        else:
            # Rebroadcast the RREQ
            self.forward_rreq(message)


    def forward_rreq(self,message):
        '''Rebroadcast an RREQ request (Called when RREQ is received by an intermediate node)'''
        msg = message[0] + ":" + self.node_id + ":" + message[2] + ":" + message[3] + ":" + message[4] + ":" + message[5] + ":" + message[6] + ":" + message[7]
        for conn in self.neighbours:
            conn.send(msg)
            logging.debug("['" + message[0] + "', 'Rebroadcasting RREQ to " + message[4] + "']")

    def send_rrep(self,rrep_dest, rrep_nh, rrep_src, rrep_int_node, dest_seq_no, hop_count):
        '''Send an RREP message back to the RREQ originator'''
        # Check if we are the destination in the RREP. If not, use the parameters passed.
        if (rrep_src == rrep_int_node):
            # Increment the sequence number and reset the hop count
            self.seq_no = self.seq_no + 1
            dest_seq_no = self.seq_no
            hop_count = 0
        # Construct the RREP message
        message_type = "RREP_MESSAGE"
        sender = self.node_id
        dest = rrep_int_node
        orig = rrep_dest
        message = message_type + ":" + sender + ":" + str(hop_count) + ":" + str(dest) + ":" + str(dest_seq_no) + ":" + str(orig)
        # Now send the RREP to the RREQ originator along the next-hop
        self.neighbours[rrep_nh].send(message)
        logging.debug("['" + message_type + "', 'Sending RREP for " + rrep_int_node + " to " + rrep_dest + " via " + rrep_nh + "']")
        pass

    def process_rrep(self,message):
        '''Process an incoming RREP message'''
        # Extract the relevant fields from the message
        message_type = message[0]
        sender = message[1]
        hop_count = int(message[2]) + 1
        message[2] = str(hop_count)
        dest = message[3]
        dest_seq_no = int(message[4])
        orig = message[5]
        logging.debug("['" + message_type + "', 'Received RREP for " + dest + " from " + sender + "']")
        # Check if we originated the RREQ. If so, consume the RREP.
        if (self.node_id == orig):
            # Update the routing table. If we have already got a route for
            # this estination, compare the hop count and update the route
            # if needed.
            if (dest in self.routing_table.keys()):
                route = self.routing_table[dest]
                route_hop_count = int(route['Hop-Count'])
                if (route_hop_count > hop_count):
                    route['Hop-Count'] = str(hop_count)
                    self.restart_route_timer(self.routing_table[dest], False)
            else:
                self.routing_table[dest] = {'Destination': dest,
                                            'Next-Hop': sender,
                                            'Seq-No': str(dest_seq_no),
                                            'Hop-Count': str(hop_count),
                                            'Status': 'Active'}
                self.restart_route_timer(self.routing_table[dest], True)
        else:
            # We need to forward the RREP. Before forwarding, update
            # information about the destination in our routing table.
            if dest in self.routing_table:
                route = self.routing_table[dest]
                route['Status'] = 'Active'
                route['Seq-No'] = str(dest_seq_no)
                self.restart_route_timer(route, False)
            else:
                self.routing_table[dest] = {'Destination': dest,
                                            'Next-Hop': sender,
                                            'Seq-No': str(dest_seq_no),
                                            'Hop-Count': str(hop_count),
                                            'Status': 'Active'}
                self.restart_route_timer(self.routing_table[dest], True)
            # Now lookup the next-hop for the source and forward it
            route = self.routing_table[orig]
            next_hop = route['Next-Hop']
            self.forward_rrep(message, next_hop)
        
    def forward_rrep(self,message,next_hop):
        '''Forward an RREP message (Called when RREP is received by an intermediate node)'''
        msg = message[0] + ":" + self.node_id + ":" + message[2] + ":" + message[3] + ":" + message[4] + ":" + message[5]
        next_hop.send(msg)
        logging.debug("['" + message[0] + "', 'Forwarding RREP for " + message[5] + " to " + next_hop + "']")

    def run(self):
        pass