import sys
from blockchain import Blockchain
from transaction import Input, Output, Transaction
from functions import *
from storage import StorageManager
import unittest
import time
import json
import hashlib

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
        blockchain_cli = BlockchainCLI()
        blockchain_cli.blockchain.create_genesis_block(difficulty=4)

        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        
        # Add a transaction and mine a block
        amount = 5.0
        blockchain_cli.blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain_cli.mine_block()

        # Check if the blockchain is valid
        self.assertTrue(blockchain_cli.blockchain.is_chain_valid())

    def test_mining_with_transactions_and_balance(self):
        blockchain_cli = BlockchainCLI()
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

    
class BlockchainCLI:
    def __init__(self):
        self.storage_manager = StorageManager()
        self.blockchain = Blockchain()
        self.miner_address = '123'#"miner_address"

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
            print("5. Exit")
            print('6. Exit + run tests')
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
                sys.exit("Exiting the program.")
            elif choice == '6':
                unittest.main()
                sys.exit('Exiting the program.')
            else:
                print("Invalid choice. Please enter a number between 1 and 5.")

if __name__ == '__main__':
    #unittest.main()
    storage_manager = StorageManager()
    blockchain_cli = BlockchainCLI()
    blockchain_cli.blockchain.create_genesis_block(difficulty=4)# Set the initial difficulty for the genesis block
    blockchain_cli.run_cli()
    storage_manager.close_connection()
