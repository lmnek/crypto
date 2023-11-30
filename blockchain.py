from collections import deque
import json
import time
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
            'nonce': self.nonce
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(hashlib.sha256(block_string.encode()).digest()).hexdigest()

    def valid_transactions(self) -> bool:
        for tx in self.transactions:
            if not tx.verify():
                return False
        return True
    
    

class Blockchain:
    def __init__(self, node):
        self.chain = deque()
        self.unconfirmed_transactions = []
        self.difficulty = 5 
        self.break_mining = False

        self.node = node
        node.set_blockchain(self)


    def create_genesis_block(self, difficulty):
        # Create the first block (genesis block) with arbitrary values
        genesis_block = Block(0, "0", [], int(time.time()), 0, difficulty)  # Set the difficulty for the genesis block
        self.proof_of_work(genesis_block)
        self.chain.append(genesis_block)

    # receive block from a peer
    def receive_block(self, block: Block):
        # skip if genesis block
        if len(self.chain) != 0:
            proof = block.compute_hash()
            last_block = self.latest_block()
            prev_hash = last_block.compute_hash()         
            # WARNING: additional validation may be required (e.g. transactions)
            if not self.is_valid_proof(self, proof) \
                or proof == prev_hash \
                or block.previous_hash != prev_hash \
                or block.timestamp >= int(time.time()) \
                or not block.valid_transactions():
                return False

        self.chain.append(block)
        self.remove_confirmed_transactions(block.transactions)
        self.break_mining = True

        return True 

    def receive_transaction(self, tx: Transaction):
        # NOTE: should do other validation?
        if not tx.verify():
            return False
        
        # NOTE: this doesnt add to currently mined blockconsider
        # consider adding it
        self.unconfirmed_transactions.append(tx)
        return True

    # Check if proof has the required number of leading zeros based on block difficulty
    def is_valid_proof(self, block, proof):
        target = "0" * block.difficulty
        return proof.startswith(target)

    def proof_of_work(self, block):
        self.break_mining = False
        while not self.break_mining:
            block.nonce += 1
            guess = block.compute_hash()
            target = "0" * block.difficulty
            if guess[:block.difficulty] == target:
                return guess

    # find unspent utxo inputs for transaction
    def find_inputs(self, sender, amount):
        # TODO:
        return amount, []

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
            self.node.new_transaction(transaction)
            return transaction
        return None

    # update uncormined transactions after new block
    def remove_confirmed_transactions(self, confirmed_transactions):
        confirmed_txids = {tx.compute_txid() for tx in confirmed_transactions}
        self.unconfirmed_transactions = [tx for tx in self.unconfirmed_transactions if tx.compute_txid() not in confirmed_txids]

    def mine(self, miner_address):
        if not self.unconfirmed_transactions:
            print("No transactions to mine.")
            return False

        last_block = self.chain[-1]
        new_block = Block(
            index=last_block.index + 1,
            previous_hash=last_block.compute_hash(),
            transactions=self.unconfirmed_transactions,
            timestamp=int(time.time()),
            nonce=0,
            difficulty=self.dynamic_difficulty(), # by average time of last 20 blocks
        )
        proof = self.proof_of_work(new_block)

        if proof:
            self.chain.append(new_block) # add mined block
            self.remove_confirmed_transactions(new_block.transactions)
            self.create_coinbase_transaction(miner_address, amount=1)  # Reward the miner
            self.node.new_block(new_block) # transmit block to peers

        return new_block.index

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            if current_block.previous_hash != previous_block.compute_hash():
                return False
        return True

    def dynamic_difficulty(self):
        if len(self.chain) > 20:
            total_time_diff = 0
            for i in range(len(self.chain) - 1, len(self.chain) - 21, -1):
                time_diff = self.chain[i].timestamp - self.chain[i - 1].timestamp
                total_time_diff += time_diff

            average_time_diff = total_time_diff / 20
            required_blockchain_difficulty = self.difficulty * average_time_diff // 1200  # 1 min to generate 1 block
            return required_blockchain_difficulty

        return self.difficulty  # if block < 20 return 4

    def calculate_cumulative_difficulty(self):
        cumulative_difficulty = 0
        for block in self.chain:
            cumulative_difficulty += 2 ** block.difficulty
        return cumulative_difficulty

    def disconnect_node(self):
        self.node.close()

    def latest_block(self):
        if len(self.chain) == 0:
            return None
        return self.chain[-1]

