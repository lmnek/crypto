import sys
from blockchain import Blockchain
from transaction import Input, Output, Transaction
from functions import *
from storage import StorageManager
from node import Node
import unittest
import time
import jsonpickle
import json

HOST='127.0.0.1'
PORT=2222
SEED_NODES = [('127.0.0.1', 6005)]

# Test suite
#unittest.main()
class TestBlockchain(unittest.TestCase):
    def test_transaction_creation_and_verification(self):
        private_key, address = generate_address()
        public_key = derive_public_key(bytes.fromhex(private_key))

        input = Input("previous_txid", 0)
        output = Output(address, 10)
        transaction = Transaction([input], [output])

        transaction.sign(private_key)
        self.assertTrue(transaction.verify())

    def test_blockchain_creation_and_mining(self):
        blockchain_cli = BlockchainCLI(PORT)
        blockchain_cli.blockchain.create_genesis_block(difficulty=4)

        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        
        # Add a transaction and mine a block
        amount = 5.0
        blockchain_cli.blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain_cli.mine_block()

        # Check if the blockchain is valid
        self.assertTrue(blockchain_cli.blockchain.is_chain_valid())

        blockchain_cli.blockchain.disconnect_node()

    def test_mining_with_transactions_and_balance(self):
        blockchain_cli = BlockchainCLI(PORT + 1)
        blockchain_cli.blockchain.create_genesis_block(difficulty=4)

        # Add a transaction and mine a block
        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        amount = 5.0
        blockchain_cli.blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain_cli.mine_block()

        # Check if the blockchain is valid
        self.assertTrue(blockchain_cli.blockchain.is_chain_valid())

        # Check if the miner's balance has increased
        blockchain_cli.print_miner_address()
        self.assertTrue(True)  

        blockchain_cli.blockchain.disconnect_node()

    
class BlockchainCLI:
    def __init__(self, port):
        self.storage_manager = StorageManager()
        self.miner_address = '123'#"miner_address"

        # decide how to connect to network
        seed_node = input('Start seed node or normal node? (s/n)') == 's'
        if not port:
            if seed_node:
                self.node = Node(*SEED_NODES[0]) # start seed node
            else:
                self.node = Node(HOST, int(input('Port: ')))
                for seed in SEED_NODES:
                    try:
                        seed_peer = self.node.connect_to_peer(*seed)
                    except Exception as e:
                        print(f'Error connecting to seed node: {e}')
        else:
            self.node = Node(HOST, port)

        self.blockchain = Blockchain(self.node)

        # NEED TO BE CREATED ONLY ONCE -> then shared to other nodes
        if seed_node:
            self.blockchain.create_genesis_block(difficulty=4) # Set the initial difficulty for the genesis block

    def store_blockchain_data(self):
        self.storage_manager.store_blockchain_data(self.blockchain)

    def load_blockchain_data(self):
        return self.storage_manager.load_blockchain_data()

    def store_latest_states_in_memory(self, key, value):
        self.storage_manager.store_latest_states_in_memory(key, value)

    def load_latest_states_from_memory(self, key):
        return self.storage_manager.load_latest_states_from_memory(key)
    

    def print_blockchain(self):
        blockchain_data = {"chain": []}
        for block in self.blockchain.chain:
            txs_data = 'Genesis block' if not block.transactions else [{
                'inputs': [{'prev_tx': i.prev_txid, 'vout': i.vout} for i in tx.inputs],
                'outputs': [{'address': o.address, 'amount': o.amount} for o in tx.outputs]
            } for tx in block.transactions]

            block_data = {
                "index": block.index,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block.timestamp)),
                "data": txs_data,
                "previousHash": block.previous_hash,
                "merkleRoot": block.merkle_root,
                "hash": block.compute_hash(),
                "difficulty": block.difficulty,
                "nonce": block.nonce,
            }
            blockchain_data["chain"].append(block_data)

        print(json.dumps(blockchain_data, indent=2))

    def print_miner_address(self):
        balance = 0
        print(f"Balance for {self.miner_address}:")
        for block in self.blockchain.chain:
            for transaction in block.transactions:
                for output in transaction.outputs:
                    if output.address == self.miner_address:
                        balance += output.amount

        print(f"{balance} coins\n")

    def mine_block(self):
        print("Mining new block...")
        new_block_index = self.blockchain.mine(self.miner_address)
        print(f"Block #{new_block_index} mined.")

    def run_cli(self):
        while True:
            print("\nChoose an option:")
            print("1. Mine a block with a transaction")
            print("2. Check current blockchain")
            print("3. Check miner address balance")
            print("4. Print blockchain data from database")
            print("5. Print network info")
            print("6. Exit")
            choice = input("Enter your choice (1-6): ")

            if choice == '1':
                sender_private_key, sender = generate_address()
                print(f'Generated sender address and private key: {sender}')
                recipient = input("Enter recipient address: ")
                amount = float(input("Enter transaction amount: "))
                self.blockchain.create_transaction(sender, recipient, amount, sender_private_key)
                self.mine_block()
            elif choice == '2':
                self.print_blockchain()
            elif choice == '3':
                self.print_miner_address()
            elif choice == '4':
                self.store_blockchain_data()
                limit = int(input("Enter the limit for printing blockchain data: "))
                self.storage_manager.print_blockchain_data(limit)
            elif choice == '5':
                print("\nChoose an option:")
                print("1. Print peer list")
                choice = input("Enter your choice (1-1): ")
                match choice:
                    case '1':
                        data = self.blockchain.node.listen_ports
                        print(jsonpickle.encode(data, indent=2))
                    case _:
                        print("Invalid choice")

            elif choice == '6':
                return
            else:
                print("Invalid choice. Please enter a number between 1 and 5.")

if __name__ == '__main__':
    if input('Run tests?(y/n)') == 'y':
        unittest.main()
    else:
        storage_manager = StorageManager()
        blockchain_cli = BlockchainCLI(None)
        blockchain_cli.run_cli()
        blockchain_cli.blockchain.disconnect_node()
        storage_manager.close_connection()
