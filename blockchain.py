import time
from collections import deque
import json
import hashlib
from transaction import*

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
        if not self.transactions:
            return hashlib.sha256(b"").hexdigest()

        transaction_hashes = [tx.compute_txid() for tx in self.transactions]

        while len(transaction_hashes) > 1:
            next_level_hashes = []

            for i in range(0, len(transaction_hashes), 2):
                # If there is an odd number of transaction hashes, handle the last one separately
                if i + 1 == len(transaction_hashes):
                    combined_hash = transaction_hashes[i] + transaction_hashes[i]
                else:
                    combined_hash = transaction_hashes[i] + transaction_hashes[i + 1]

                next_level_hashes.append(hashlib.sha256(combined_hash.encode()).hexdigest())

            transaction_hashes = next_level_hashes

        return transaction_hashes[0]

    def compute_hash(self):
        block_data = {
            'index': self.index,
            'root': self.merkle_root,
            'timestamp': self.timestamp,
            'previous_hash': self.previous_hash,
            'difficulty': self.difficulty,
            'nonce': self.nonce,
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(hashlib.sha256(block_string.encode()).digest()).hexdigest()
    
    

class Blockchain:
    def __init__(self):
        self.chain = deque()
        self.unconfirmed_transactions = []
        self.blockchain_difficulty = 4

    def create_genesis_block(self,difficulty):
        # Create the first block (genesis block) with arbitrary values
        genesis_block = Block(0, "0", [], int(time.time()), 0, difficulty)  # Set the difficulty for the genesis block
        proof = self.proof_of_work(genesis_block)
        genesis_block.hash = proof
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

    # find unspent utxo inputs for transaction
    def find_inputs(self, sender, amount):
        # TODO:
        return 0, []

    def create_coinbase_transaction(self, recipient, amount):
        outputs = [Output(recipient, amount)]
        tx = Transaction([], outputs)
        self.unconfirmed_transactions.append(tx)
        return tx

    # Create and add UTXO transaction with inputs, outputs 
    def create_transaction(self, sender, recipient, amount, sender_private_key):
        total_input_value, inputs = self.find_inputs(sender, amount)
        outputs = [Output(recipient, amount)]

        # TODO: what if insufficient funds?

        # Handle returning back to the sender
        change_amount = total_input_value - amount
        if change_amount > 0:
            outputs.append(Output(sender, change_amount))

        transaction = Transaction(inputs, outputs)
        transaction.sign(sender_private_key)
        if transaction.verify():
            self.unconfirmed_transactions.append(transaction)
            return transaction
        return None

    def mine(self, miner_address):
        if not self.unconfirmed_transactions:
            print("No transactions to mine.")
            return False

        last_block = self.chain[-1]
        new_block = Block(
            index=last_block.index + 1,
            previous_hash=last_block.hash,
            transactions=self.unconfirmed_transactions,
            timestamp=int(time.time()),
            nonce=0,
            difficulty=self.dynamic_difficulty(), # by average time of last 20 blocks
        )

        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)
        self.unconfirmed_transactions = []  # Clear unconfirmed transactions
        self.create_coinbase_transaction(miner_address, amount=1)  # Reward the miner - coinbase transaction
        # TODO: somewhere here, transfer new block to peers?
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

    def dynamic_difficulty(self):
        if len(self.chain) > 20:
            total_time_diff = 0
            for i in range(len(self.chain) - 1, len(self.chain) - 21, -1):
                time_diff = self.chain[i].timestamp - self.chain[i - 1].timestamp
                total_time_diff += time_diff

            average_time_diff = total_time_diff / 20
            required_blockchain_difficulty = self.blockchain_difficulty * average_time_diff // 1200  # 1 min to generate 1 block
            return required_blockchain_difficulty

        return self.blockchain_difficulty  # if block < 20 return 4

