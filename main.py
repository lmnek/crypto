import sys
from blockchain import Blockchain
from transaction import Input, Output, Transaction
from functions import *
import unittest

# Test suite
# unittest.main()
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


class BlockchainCLI:
    def __init__(self):
        self.blockchain = Blockchain()
        self.blockchain.create_genesis_block()
        self.miner_address = "miner_address"

    def print_blockchain(self):
        print("Blockchain:")
        for block in self.blockchain.chain:
            print(f"Block #{block.index} - Hash: {block.hash}")
            print("Transactions:")
            for transaction in block.transactions:
                print(f"  {transaction}")
            print("\n")

    def print_miner_address(self):
        balance = 0
        print(f"Balance for {self.miner_address}:")
        for block in self.blockchain.chain:
            for transaction in block.transactions:
                if transaction['recipient'] == self.miner_address:
                    balance += transaction['amount']
                if transaction['sender'] == self.miner_address:
                    balance -= transaction['amount']
        print(f"{balance} coins\n")

    def mine_block(self):
        print("Mining new block...")
        new_block_index = self.blockchain.mine(self.miner_address)
        print(f"Block #{new_block_index} mined.")

    def run_cli(self):
        while True:
            print("\nChoose an option:")
            print("1. Mine a block")
            print("2. Check current blockchain")
            print("3. Check miner address balance")
            print("4. Exit")

            choice = input("Enter your choice (1-4): ")

            if choice == '1':
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
    blockchain_cli = BlockchainCLI()
    blockchain_cli.run_cli()
