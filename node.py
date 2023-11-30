import socket
import threading
import json
import jsonpickle
import time

from blockchain import hashlib
from threading import Event


SEED_NODES = [('127.0.0.1', 6004)]

def str_to_Message(string):
    json_obj = json.loads(string.decode())
    return Message(**json_obj)

class Message:
    def __init__(self, m_type, data, broadcast=False) -> None:
        self.m_type = m_type
        self.broadcast = broadcast 
        self.data = data

    def to_str(self):
        return json.dumps(self.__dict__).encode()
    
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

        self.processed_messages = set() # list of IDs
        print(f"Node started on {self.host}:{self.port}")

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
        print('node closed')


    
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
        listening_port = client.recv(1024).decode('utf-8')
        print('Received port: ' + listening_port)
        send_address = client.getpeername()
        self.peers.add(send_address)
        self.listen_ports[send_address] = (send_address[0], listening_port)
        self.peer_sockets[send_address] = client

        self.handle_client_connection(client, address)


    def handle_client_connection(self, client, address):
        print(f"Connected to {address}")
        client.settimeout(5)
        while self.active:
            try:
                message_str = receive_complete_message(client)

                # client disconnected
                if not message_str:
                    break

                message = str_to_Message(message_str)
                self.handle_message(client, message)
            except Exception as e:
                print(f'Node connection error: {e}')
                break
        
        client.close()
        if address in self.peers:
            self.peers.remove(address)
            del self.peer_sockets[address]
            del self.listen_ports[address]
            print(f'Disconnected from: {address}')

    def periodic_sync(self, interval=600):  # Example interval of 10 minutes
        while self.active:
            print('Started syncronizing')
            self.sync_blockchain()
            if len(self.peers) < self.MAX_CONNETIONS:
                self.broadcast(Message('GET_PEERS', None))
            time.sleep(interval)

    def sync_blockchain(self):
        self.broadcast(Message('GET_LATEST_BLOCK', None))
        

    def handle_message(self, client, message: Message):
        print(f'Received: {message.m_type}, from {client.getpeername()}')

        if message.broadcast and message.get_id() in self.processed_messages:
            print('-> already processed message')
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
                chain = self.blockchain.chain
                if len(chain) > idx:
                    block = jsonpickle.encode(chain[idx])
                    self.send_to_peer(client, Message('BLOCK', block))
            case "BLOCK":
                block = jsonpickle.decode(message.data)
                if self.blockchain.receive_block(block):
                    self.send_to_peer(client, Message('GET_BLOCK', block.index + 1))
                else:
                    pass # ????

            case "GET_LATEST_BLOCK" :
                block = self.blockchain.latest_block()
                m = Message('LATEST_BLOCK', jsonpickle.encode(block))
                self.send_to_peer(client, m)
            case "LATEST_BLOCK" :
                received_block = message.data
                local_block = self.blockchain.get_latest_block()

                # TODO: handle forks
                if received_block.index > local_block.index:
                    self.send_to_peer(client, Message('GET_BLOCK', local_block.index))

            # TODO: handle forks with highest cumulative difficulty
            case "GET_CONSENSUS_DATA" :
                pass
            case "CONSESUS_DATA" :
                pass
            case _ :
                print('Unknown message type')


        # if message.broadcast and not message.get_id() in self.processed_messages:
        #    self.broadcast(message)


    def connect_to_peer(self, peer_host, peer_port):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.settimeout(10)
        peer_socket.setblocking(True)
        address = (peer_host, peer_port)
        peer_socket.connect(address)

        # share listening port
        peer_socket.sendall(str(self.port).encode('utf-8'))

        self.peers.add(address)
        self.listen_ports[address] = address
        self.peer_sockets[address] = peer_socket 
        print(f"Connected to peer {peer_host}:{peer_port}")

        threading.Thread(target=self.handle_client_connection, args=(peer_socket, address)).start()
        return peer_socket

    def send_to_peer(self, peer, message):
        print(f'Sending: {message.m_type}, to {peer.getpeername()}')
        try:
            peer.sendall(message.to_str())
        except Exception as e:
            print(f"Error sending message to peer: {e}")

    def broadcast(self, message: Message):
        message.broadcast = True
        self.processed_messages.add(message.get_id())
        for peer in self.peers:
            peer_socket = self.peer_sockets.get(peer)
            if peer_socket:
                self.send_to_peer(peer, message)

    def new_block(self, block):
        json_str = jsonpickle.encode(block)
        self.broadcast(Message('NEW_BLOCK', json_str))

    def new_transaction(self, transaction):
        json_str = jsonpickle.encode(transaction)
        self.broadcast(Message('NEW_TRANSACTION', json_str))

    def get_peer_list(self, client):
        self.send_to_peer(client, Message("GET_PEERS", None))

    def handle_peer_list(self, peer_list):
        print(peer_list)
        print(self.peers)
        print(self.listen_ports.values())
        for peer in peer_list:
            peer_tuple = (peer[0], int(peer[1]))
            if peer_tuple not in self.listen_ports.values() and peer_tuple != (self.host, self.port): 
                print(f"New peer discovered: {peer_tuple}")
                if len(self.peers) >= self.MAX_CONNETIONS:
                    print('-> Already have max connections')
                    continue

                try:
                    # TODO: querry for the latest block
                    self.connect_to_peer(*peer_tuple)
                except ConnectionError:
                    print(f'Failed to connect to: {peer_tuple}')

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



# -----------------------------------------------------


if __name__ == "__main__":
    if input('A seed node? (y/n)') == 'y':
        node = Node(*SEED_NODES[0])
        Event().wait() # break on keyboard input

    # TODO: run blockchain alongside

    port = int(input('Port number: '))
    node = Node('127.0.0.1', port)
    # connect to SEED_NODES first
    for seed in SEED_NODES:
        try:
            seed_peer = node.connect_to_peer(*seed)
            node.get_peer_list(seed_peer)
        except Exception as e:
            print(f'Error connecting to seed node: {e}')

    Event().wait()

    other_port = int(input('Others port number: '))
    other_peer = node.connect_to_peer('localhost', other_port)
    node.send_to_peer(other_peer, Message('HELLO', {'a': 1, 'b': 2}))
