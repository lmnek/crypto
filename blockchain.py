import time
from collections import deque
import json
import hashlib

# Inspiration from
# https://www.alibabacloud.com/blog/595314

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp, nonce, difficulty):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp
        self.nonce = nonce
        self.difficulty = difficulty
        self.merkle_root = self.calculate_merkle_root()

    def calculate_merkle_root(self):
        # Implement your Merkle tree logic here
        pass

    def compute_hash(self):
        block_string = json.dumps(self.__dict__, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = deque()
        self.unconfirmed_transactions = []

    def create_genesis_block(self):
        # Create the first block (genesis block) with arbitrary values
        genesis_block = Block(0, "0", [], int(time.time()), 0, 4)  # Difficulty set to 4 for simplicity
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    def add_block(self, block, proof):
        previous_hash = self.chain[-1].hash
        if previous_hash != block.previous_hash:
            return False

        # TODO: check for validity of chain when adding block from outside
        # TODO: update unspent UTXO list memory
        if not self.is_valid_proof(block, proof):
            return False

        block.hash = proof
        self.chain.append(block)
        return True

    def is_valid_proof(self, block, proof):
        # Check if proof has the required number of leading zeros based on block difficulty
        target = "0" * block.difficulty
        return proof.startswith(target)

    def proof_of_work(self, block):
        while True:
            block.nonce += 1
            guess = block.compute_hash()
            target = "0" * block.difficulty
            if guess[:block.difficulty] == target:
                return guess

    def add_transaction(self, sender, recipient, amount):
        # Create a new transaction and add it to unconfirmed transactions
        self.unconfirmed_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

    def mine(self, miner_address):
        if not self.unconfirmed_transactions:
            return False

        last_block = self.chain[-1]
        new_block = Block(
            index=last_block.index + 1,
            previous_hash=last_block.hash,
            transactions=self.unconfirmed_transactions,
            timestamp=int(time.time()),
            nonce=0,
            difficulty=last_block.difficulty,
        )

        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)
        self.unconfirmed_transactions = []  # Clear unconfirmed transactions
        self.add_transaction(sender="0", recipient=miner_address, amount=1)  # Reward the miner - coinbase transaction
        return new_block.index

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.hash != current_block.compute_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True
