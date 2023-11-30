from blockchain import Blockchain
from transaction import Input, Output, Transaction
from functions import *
from storage import StorageManager
from node import Node
import unittest
import time
import jsonpickle
import json
from wallet import *

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
        self.miner_private_key, self.miner_address = generate_address()
        print(f'Miner address: {self.miner_address}')

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
        self.wallet = Wallet(self.blockchain)
        # NEED TO BE CREATED ONLY ONCE -> then shared to other nodes
        if seed_node:
            self.blockchain.create_genesis_block(difficulty=4) # Set the initial difficulty for the genesis block

    def show_transactions(self):
        print("\nAll Transactions:")
        all_transactions = self.storage_manager.load_all_transactions()
        if all_transactions:
            for transaction in all_transactions:
                print(f"Transaction ID: {transaction.compute_txid()}")
                print("Inputs:")
                for inp in transaction.inputs:
                    print(f"  Prev_txid: {inp.prev_txid}, Vout: {inp.vout}, Signature: {inp.signature}, Public Key: {inp.public_key}")
                print("Outputs:")
                for out in transaction.outputs:
                    print(f"  Address: {out.address}, Amount: {out.amount}")
                print("Signature:", transaction.signature)
                print("\n")
        else:
            print("No transactions found.")
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
        print(f"Balance for {self.miner_address}:")
        print(f"{self.blockchain.get_balance(self.miner_address)} coins\n")

    def mine_block(self):
        print("Mining new block...")
        new_block_index = self.blockchain.mine(self.miner_address)
        print(f"Block #{new_block_index} mined.")

    def run_cli(self):
        mode = input("\nChoose a mode:\n1. Wallet\n2. Developer\nEnter your choice (1-2): ")
        if mode == '1':
            while True:
                print("\nChoose an option:")
                print("0. Create a new address")
                print("1. Check balance of all addresses")
                print("2. Transfer coins")
                print("3. Print all addresses in the wallet")
                print("4. Print UTXOs of all addresses")  # New option
                print("5. Exit")  # Updated option number
                choice = input("Enter your choice (0-5): ")

                if choice == '0':
                    self.wallet.create_address()
                elif choice == '1':
                    address = input('Enter the address to check the balance: ')
                    balance = self.wallet.get_balance(address)
                    print(f'Balance of {address}: {balance} coins')
                elif choice == '2':
                    sender_address = input("Enter sender address: ")
                    recipient_address = input("Enter recipient address: ")
                    amount = float(input("Enter amount to transfer: "))
                    self.wallet.transfer(sender_address, recipient_address, amount)
                elif choice == '3':
                    self.wallet.print_addresses()
                elif choice == '4':  # New option
                    self.wallet.print_utxos()
                elif choice == '5':  # Updated option number
                    return
                else:
                    print("Invalid choice. Please enter a number between 0 and 5.")
        elif mode == '2':
            while True:
                print("\nChoose an option:")
                print("0. Mine a block")
                print("1. Add a transaction as miner")
                print("2. Check current blockchain")
                print("3. Check miner address balance")
                print("4. Print blockchain data from database")
                print("5. Print network info")
                print("6. Print UTXOs (unspent)")
                print("7. Show all transaction")
                print("8. Exit")
                choice = input("Enter your choice (0-8): ")

                if choice == '0':
                    self.mine_block()
                elif choice == '1':
                    recipient = input("Enter recipient address: ")
                    amount = float(input("Enter transaction amount: "))
                    self.blockchain.create_transaction(self.miner_address, recipient, amount, self.miner_private_key)
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
                            data = list(self.blockchain.node.listen_ports.values())
                            print(jsonpickle.encode(data, indent=2))
                        case _:
                            print("Invalid choice")
                elif choice == '6':
                    utxos = [
                        {
                            'tx_id': key[0],
                            'vout': key[1],
                            'address': u.address,
                            'amount': u.amount
                        }
                    for key, u in self.blockchain.utxos.items()]
                    print(json.dumps(utxos, indent=2))

                elif choice == '7':
                    self.show_transactions()
                elif choice == '8':
                    return
                else:
                    print("Invalid choice. Please enter a number between 0 and 7.")
        else:
            print("Invalid mode. Please enter a number between 1 and 2.")


if __name__ == '__main__':
    if input('Run tests?(y/n)') == 'y':
        unittest.main()
    else:
        storage_manager = StorageManager()
        blockchain_cli = BlockchainCLI(None)
        blockchain_cli.run_cli()
        blockchain_cli.blockchain.disconnect_node()
        storage_manager.close_connection()