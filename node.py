import socket
import threading
import json
import jsonpickle
import time

from blockchain import hashlib

def str_to_Message(string):
    json_obj = json.loads(string.decode())
    return Message(**json_obj)

class Message:
    def __init__(self, m_type, data, broadcast=False) -> None:
        self.m_type = m_type
        self.broadcast = broadcast 
        self.data = data

    def to_str(self):
        return (json.dumps(self.__dict__) + '\r\n').encode()
    
    def get_id(self):
        return hashlib.sha256(self.to_str()).hexdigest()
        

# WARNING: python collections are not threadsafe by default
class Node:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.active = True # flag to control threads

        self.peers = set() # addresses
        self.listen_ports = {} # map addresses to listening ports of peers
        self.peer_sockets = {} # mapping addresses to sockets

        self.node = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.node.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.node.bind((self.host, self.port))
        self.node.listen(5)
        self.MAX_CONNETIONS=5

        self.log = True 
        self.processed_messages = set() # list of IDs
        if self.log: print(f"Node started on {self.host}:{self.port}")

        # start listening for connections
        listener_thread = threading.Thread(target=self.listen_for_incoming_connections)
        listener_thread.daemon = True
        listener_thread.start()

        # Start periodic synchronization in a separate thread
        sync_thread = threading.Thread(target=self.periodic_sync)
        sync_thread.daemon = True
        sync_thread.start()

    
    def close(self):
        self.active = False
        # close sockets
        self.node.close()
        for peer_socket in self.peer_sockets.values():
            peer_socket.close()
        if self.log: print('node closed')


    
    def set_blockchain(self, blockchain):
        self.blockchain = blockchain

    def listen_for_incoming_connections(self):
        while self.active:
            client, address = self.node.accept()
            client.settimeout(60)
            client.setblocking(True)
            threading.Thread(target=self.handle_client_connection_and_port, args=(client, address)).start()

    # Need to get listening port from peer
    def handle_client_connection_and_port(self, client, address):
        send_address = client.getpeername()
        self.peers.add(send_address)
        self.peer_sockets[send_address] = client

        self.handle_client_connection(client, address)


    def handle_client_connection(self, client, address):
        if self.log: print(f"Connected to {address}", flush=True)

        self.send_to_peer(client, Message('GET_LATEST_BLOCK', None)) # ask after connecting
        self.get_peer_list(client)
    
        while self.active:
            data = b''
            try:
                data += receive_complete_message(client)

                # client disconnected?
                if not data: 
                    break
                # avoid mixing of packets
                if not data.endswith(b'\r\n'):
                    continue

                messages = data.split(b'\r\n')
                for m_bytes in messages:
                    if m_bytes == b'':
                        continue
                    message = str_to_Message(m_bytes)
                    self.handle_message(client, message)
            except Exception as e:
                if self.log: print(f'Node connection error: {e}')
                break
        
        client.close()
        if address in self.peers:
            self.peers.remove(address)
            del self.peer_sockets[address]
            del self.listen_ports[address]
            if self.log: print(f'Disconnected from: {address}')

    def periodic_sync(self, interval=600):  # Example interval of 10 minutes
        while self.active:
            self.broadcast(Message('GET_LATEST_BLOCK', None))
            if len(self.peers) < self.MAX_CONNETIONS:
                self.broadcast(Message('GET_PEERS', None))
            time.sleep(interval)

    def handle_message(self, client, message: Message):
        if self.log: print(f'Received: {message.m_type}, from {client.getpeername()}', flush=True)

        if message.data and message.broadcast and message.get_id() in self.processed_messages:
            if self.log: print('-> already processed message')
            return

        match message.m_type:
            case "GET_PEERS" :
                m = Message("PEERS_LIST", list(self.listen_ports.values()))
                self.send_to_peer(client, m)
            case "PEERS_LIST" :
                self.handle_peer_list(message.data)

            case "NEW_TRANSACTION" : 
                new_transaction = jsonpickle.decode(message.data)
                if self.blockchain.receive_transaction(new_transaction):
                    self.broadcast(message)
            case "NEW_BLOCK" :
                new_block = jsonpickle.decode(message.data)
                if self.blockchain.receive_block(new_block):
                    self.broadcast(message)

            case "GET_BLOCK" :
                idx = int(message.data)
                if idx == -1:
                    idx += 1
                chain = self.blockchain.chain
                if len(chain) > idx:
                    block = jsonpickle.encode(chain[idx])
                    self.send_to_peer(client, Message('BLOCK', block))
            case "BLOCK":
                block = jsonpickle.decode(message.data) 
                if self.blockchain.receive_block(block):
                    self.send_to_peer(client, Message('GET_BLOCK', block.index + 1))
                else:
                    self.send_to_peer(client, Message('GET_CONSENSUS_DATA', None))

            case "GET_LATEST_BLOCK" :
                block = self.blockchain.latest_block()
                m = Message('LATEST_BLOCK', jsonpickle.encode(block))
                self.send_to_peer(client, m)
            case "LATEST_BLOCK" :
                received_block = jsonpickle.decode(message.data)
                if not received_block:
                    return

                local_block = self.blockchain.latest_block()
                local_idx = local_block.index if local_block else -1

                if received_block.index > local_idx:
                    self.send_to_peer(client, Message('GET_BLOCK', local_idx))
                if (received_block.index == local_idx \
                        and received_block.compute_hash() != local_block.compute_hash()) \
                    or received_block.index < local_idx:
                    self.send_to_peer(client, Message('GET_CONSENSUS_DATA', None))

            # Fork handling with cumulative difficulty of chain 
            case "GET_CONSENSUS_DATA" :
                chain_hashes = [{'index': block.index, 'hash': block.compute_hash()} for block in self.blockchain.chain]
                data = {'chain_hashes': chain_hashes, 'cum_diff': self.blockchain.calculate_cumulative_difficulty()}
                self.send_to_peer(client, Message('CONSENSUS_DATA', json.dumps(data)))
            case "CONSENSUS_DATA" :
                data = json.loads(message.data)
                self.handle_consensus(client, data['chain_hashes'], data['cum_diff'])

            case "PORT":
                address = client.getpeername()
                self.listen_ports[address] = (address[0], int(message.data))
            case _ :
                if self.log: print('Unknown message type')


        # if message.broadcast and not message.get_id() in self.processed_messages:
        #    self.broadcast(message)

    def handle_consensus(self, client, chain_hashes, other_cum_diff):
        cum_diff = self.blockchain.calculate_cumulative_difficulty()
        last_common_block_idx = self.last_common_block(chain_hashes)
        if cum_diff > other_cum_diff:
            # we win fork -> they need to sync
            block = jsonpickle.encode(self.blockchain.chain[last_common_block_idx + 1])
            self.send_to_peer(client, Message('BLOCK', block))
        elif cum_diff < other_cum_diff:
            # peer wins fork -> we need to sync
            self.send_to_peer(client, Message('GET_BLOCK', last_common_block_idx + 1))

    def last_common_block(self, chain_hashes):
        min_len = min(len(chain_hashes), len(self.blockchain.chain))
        for i in range(min_len - 1):
            if chain_hashes[i]['hash'] != self.blockchain.chain[i].compute_hash():
                return i - 1
        return min_len 

    

    def connect_to_peer(self, peer_host, peer_port):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.setblocking(True)
        address = (peer_host, peer_port)
        peer_socket.connect(address)

        # share listening port
        self.send_to_peer(peer_socket, Message("PORT", self.port))

        self.peers.add(address)
        self.listen_ports[address] = address
        self.peer_sockets[address] = peer_socket 
        if self.log: print(f"Connected to peer {peer_host}:{peer_port}")

        threading.Thread(target=self.handle_client_connection, args=(peer_socket, address)).start()

        return peer_socket

    def send_to_peer(self, peer, message):
        if self.log: print(f'Sending: {message.m_type}, to {peer.getpeername()}')
        try:
            peer.sendall(message.to_str()) 
        except Exception as e:
            if self.log: print(f"Error sending message to peer: {e}")

    def broadcast(self, message: Message):
        message.broadcast = True
        self.processed_messages.add(message.get_id())
        for peer in self.peers:
            peer_socket = self.peer_sockets.get(peer)
            if peer_socket:
                self.send_to_peer(peer_socket, message)

    def new_block(self, block):
        json_str = jsonpickle.encode(block)
        self.broadcast(Message('NEW_BLOCK', json_str))

    def new_transaction(self, transaction):
        json_str = jsonpickle.encode(transaction)
        self.broadcast(Message('NEW_TRANSACTION', json_str))

    def get_peer_list(self, client):
        self.send_to_peer(client, Message("GET_PEERS", None))

    def handle_peer_list(self, peer_list):
        for peer in peer_list:
            peer_tuple = (peer[0], int(peer[1]))
            if peer_tuple not in self.listen_ports.values() and peer_tuple != (self.host, self.port): 
                if self.log: print(f"New peer discovered: {peer_tuple}")
                if len(self.peers) >= self.MAX_CONNETIONS:
                    if self.log: print('-> Already have max connections')
                    continue

                try:
                    self.connect_to_peer(*peer_tuple)
                except ConnectionError:
                    if self.log: print(f'Failed to connect to: {peer_tuple}')

# Account for large messages with fragmentation
def receive_complete_message(client_socket):
    data = b''
    while True:
        part = client_socket.recv(1024)
        if not part:
            return None

        data += part
        # Either 0 or end of data
        if len(part) < 1024:
            break
    return data

