import sys
from blockchain import Blockchain
from transaction import Input, Output, Transaction
from functions import *
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

        print('private key: ' + private_key)
        print('address: ' + address)

        input = Input("previous_txid", 0)
        output = Output(address, 10)
        transaction = Transaction([input], [output])

        transaction.sign(private_key)
        self.assertTrue(transaction.verify())

    def test_blockchain_creation_and_mining(self):
        blockchain_cli = BlockchainCLI()
        blockchain_cli.blockchain.create_genesis_block(difficulty=4)

        # Add a transaction and mine a block
        sender = "sender_address"
        recipient = "recipient_address"
        amount = 5.0
        blockchain_cli.blockchain.add_transaction(sender, recipient, amount)
        blockchain_cli.mine_block()

        # Check if the blockchain is valid
        self.assertTrue(blockchain_cli.blockchain.is_chain_valid())

    def test_mining_with_transactions_and_balance(self):
        blockchain_cli = BlockchainCLI()
        blockchain_cli.blockchain.create_genesis_block(difficulty=4)

        # Add a transaction and mine a block
        sender = "sender_address"
        recipient = "recipient_address"
        amount = 5.0
        blockchain_cli.blockchain.add_transaction(sender, recipient, amount)
        blockchain_cli.mine_block()

        # Check if the blockchain is valid
        self.assertTrue(blockchain_cli.blockchain.is_chain_valid())

        # Check if the miner's balance has increased
        blockchain_cli.print_miner_address()
        self.assertTrue(True)  # Add your own assertion based on your logic

    
class BlockchainCLI:
    def __init__(self):
        self.blockchain = Blockchain()
        self.miner_address = '123'#"miner_address"

    def print_blockchain(self):
        blockchain_data = {"chain": []}
        for block in self.blockchain.chain:
            block_data = {
                "index": block.index,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block.timestamp)),
                "data": {"amount": block.transactions[0].outputs[0].amount} if block.transactions else "Genesis block of simple chain",
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
            print("4. Exit")

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
                sender = input("Enter sender address: ")
                recipient = input("Enter recipient address: ")
                amount = float(input("Enter transaction amount: "))
                self.blockchain.add_transaction(sender, recipient, amount)
                self.mine_block()
            elif choice == '2':
                self.print_blockchain()
            elif choice == '3':
                self.print_miner_address()
            elif choice == '4':
                sys.exit("Exiting the program.")
            else:
                print("Invalid choice. Please enter a number between 1 and 4.")

if __name__ == '__main__':
    #unittest.main()
    blockchain_cli = BlockchainCLI()
    blockchain_cli.blockchain.create_genesis_block(difficulty=4)# Set the initial difficulty for the genesis block
    blockchain_cli.run_cli()
