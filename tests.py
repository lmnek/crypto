import unittest
import time
from blockchain import Blockchain, Block
from node import Node
from functions import *
from transaction import *

HOST='127.0.0.1'

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
        node = Node(HOST, 2222)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        
        # Add a transaction and mine a block
        amount = 5.0
        blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain.mine(sender)

        # Check if the blockchain is valid
        self.assertTrue(blockchain.is_chain_valid())
        blockchain.quit()

    def test_mining_with_transactions_and_balance(self):
        node = Node(HOST, 2223)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        # Add a transaction and mine a block
        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        amount = 5.0
        blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain.mine(sender)

        # Check if the blockchain is valid
        self.assertTrue(blockchain.is_chain_valid())
        blockchain.quit()


    def test_blockchain_validation(self):
        node = Node(HOST, 2224)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        sender_private_key, sender = generate_address()
        recipient = "recipient_address"
        amount = 5.0
        blockchain.create_transaction(sender, recipient, amount, sender_private_key)
        blockchain.mine(sender)

        self.assertTrue(blockchain.is_chain_valid())
        blockchain.quit()

    def test_orphan_block_handling(self):
        node = Node(HOST, 2225)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        orphan_block = Block(5, "some_hash", [], int(time.time()), 0, 4)
        self.assertFalse(blockchain.receive_block(orphan_block))
        blockchain.quit()

    def test_fork_resolution(self):
        node = Node(HOST, 2226)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        # Mining some blocks to form a chain
        for _ in range(3):
            sender_private_key, sender = generate_address()
            recipient = "recipient_address"
            amount = 5.0
            blockchain.create_transaction(sender, recipient, amount, sender_private_key)
            blockchain.mine(sender)

        # Creating a forked block
        forked_block = Block(1, blockchain.chain[0].compute_hash(), [], int(time.time()), 0, 4)
        self.assertFalse(blockchain.receive_block(forked_block))
        blockchain.quit()

    def test_transaction_pool_update(self):
        node = Node(HOST, 2227)
        blockchain = Blockchain(node)
        blockchain.create_genesis_block(difficulty=4)

        # Creating and adding transactions
        for _ in range(5):
            sender_private_key, sender = generate_address()
            recipient = "recipient_address"
            amount = 1.0
            transaction = blockchain.create_transaction(sender, recipient, amount, sender_private_key)
            self.assertIsNotNone(transaction)

        # Mining a block to clear the transaction pool
        blockchain.mine("miner_address")
        self.assertEqual(len(blockchain.unconfirmed_transactions), 0)
        blockchain.quit()
