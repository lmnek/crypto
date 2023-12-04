from blockchain import Blockchain
from functions import *
from storage import StorageManager
from node import Node, threading
import unittest
import time
import jsonpickle
import json
from wallet import *

HOST='127.0.0.1' # local for testing
SEED_NODES = [('127.0.0.1', 6005)] # can be multiple ones
    
class BlockchainCLI:
    def __init__(self):
        self.storage_manager = StorageManager()

        # decide how to connect to network
        seed_node = input('Start seed node or normal node? (s/n)') == 's'
        if seed_node:
            self.node = Node(*SEED_NODES[0]) # start seed node
        else:
            self.node = Node(HOST, int(input('Port: ')))
            for seed in SEED_NODES:
                try:
                    self.node.connect_to_peer(*seed)
                except Exception as e:
                    print(f'Error connecting to seed node: {e}')
        
        # Load blockchain data from MongoDB
        #self.blockchain = self.storage_manager.load_blockchain_data()

        self.blockchain = Blockchain(self.node)
        self.wallet = Wallet(self.blockchain)
        self.mine = False

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

    def mining_thread(self):
        while True: 
            if self.mine:
                self.blockchain.mine(self.miner_address)
            time.sleep(1)

    def run_cli(self):
        time.sleep(2)
        mode = input("\nChoose a mode:\n1. Wallet\n2. Developer\nEnter your choice (1-2): ")
        if mode == '1':
            self.blockchain.node.log = False
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
                elif choice == '4':  
                    self.wallet.print_utxos()
                elif choice == '5':  
                    self.blockchain.break_mining = True
                    self.mine = False
                    self.blockchain.quit()
                    return
                else:
                    print("Invalid choice. Please enter a number between 0 and 5.")
        elif mode == '2':
            self.miner_private_key, self.miner_address = generate_address()
            print(f'Miner address: {self.miner_address}')
            self.mine = False 
            threading.Thread(target=self.mining_thread).start()
            while True:
                print("\nChoose an option:")
                print("0. Mine a block")
                print("1. Add a transaction as miner")
                print("2. Check current blockchain")
                print("3. Check miner address balance")
                print("4. Print network info")
                print("6. Print UTXOs (unspent)")
                print("7. Start/stop mining")
                print("8. Start/stop network logs")
                print("9. Show transaction")
                print("10. Exit")
                choice = input("Enter your choice (0-10): ")

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
                    self.storage_manager.store_blockchain_data(self.blockchain)
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
                    utxos = []
                    for key in self.blockchain.utxos.scan_iter("utxo:*"):
                        utxo_data = str(self.blockchain.utxos.get(key))
                        if utxo_data is not None:
                            utxo = json.loads(utxo_data)
                            _, prev_txid, vout_str = key.decode('utf-8').split(':')
                            utxos.append({
                                'tx_id': prev_txid,
                                'vout': int(vout_str),
                                'address': utxo['address'],
                                'amount': utxo['amount']
                            })
                    print(json.dumps(utxos, indent=2))
                elif choice == '7':
                   self.mine = not self.mine 
                elif choice == '8':
                   self.blockchain.node.log = not self.blockchain.node.log 
                elif choice =='9':
                    self.show_transactions()
                elif choice == '10':
                    self.blockchain.break_mining = True
                    self.mine = False
                    self.blockchain.quit()
                    return
                else:
                    print("Invalid choice. Please enter a number between 0 and 10.")
        else:
            print("Invalid mode. Please enter a number between 1 and 2.")


if __name__ == '__main__':
    if input('Run tests? (y/n)') == 'y':
        unittest.main()
    else:
        blockchain_cli = BlockchainCLI()
        blockchain_cli.run_cli()
