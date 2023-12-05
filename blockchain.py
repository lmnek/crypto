from collections import deque
import json
import time
import hashlib
from transaction import*
from storage import StorageManager
import redis

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

    
    def valid_transactions(self, utxos) -> bool:
        used_utxos = set()
        for tx in self.transactions:
            input_value = 0
            output_value = sum(output.amount for output in tx.outputs)

            for input in tx.inputs:
                key = (input.prev_txid, input.vout)
                #  Avoid double-spend
                if key not in utxos or key in used_utxos:
                    return False

                input_value += utxos[key].amount
                used_utxos.add(key)

            if not tx.verify() or \
                (len(tx.inputs) > 0 and input_value < output_value):
                return False

        return True
    

class Blockchain:
    def __init__(self, node):
        self.chain = deque()
        self.unconfirmed_transactions = []
        self.difficulty = 5 
        self.break_mining = False
        self.utxos = redis.Redis(host='localhost', port=6379, db=0) # store unspent UTXOs, key is (txid, vout)
        self.storage_manager = StorageManager()
        self.node = node
        node.set_blockchain(self)

    
    def create_genesis_block(self, difficulty):
        # Create the first block (genesis block) with arbitrary values
        genesis_block = Block(0, "0", [], int(time.time()), 0, difficulty)  # Set the difficulty for the genesis block
        self.proof_of_work(genesis_block)
        self.chain.append(genesis_block)

    # receive block from a peer
    def receive_block(self, block: Block):
        # need to restructure blockchain after fork
        if block.index < self.chain.index:
            return self.receive_past_block(block)
        # skip if fetching genesis block
        if len(self.chain) != 0:
            proof = block.compute_hash()
            last_block = self.latest_block()
            prev_hash = last_block.compute_hash()         
            if not self.is_valid_proof(self, proof) \
                or proof == prev_hash \
                or block.previous_hash != prev_hash \
                or block.timestamp >= int(time.time()) \
                or block.calculate_merkle_root() != block.merkle_root \
                or not block.valid_transactions(self.utxos):
                return False

        self.chain.append(block)
        self.update_utxos(block)
        self.remove_confirmed_transactions(block.transactions)
        self.break_mining = True

        return True 

    def receive_past_block(self, block: Block):
        if block.index != self.chain[0].index - 1:
            return False
        self.chain.append(block)
        if not self.reorganize_chain(block.index):
            self.chain.pop()
            return False
        self.rebuild_utxos()
        return True

    def reorganize_chain(self, fork_index):
        for i in range(fork_index, len(self.chain)):
            current_block = self.chain[i]
            if i > 0:
                previous_block = self.chain[i - 1]
                if current_block.previous_hash != previous_block.compute_hash():
                    return False
        for i in range(fork_index, len(self.chain)):
            current_block = self.chain[i]
            if i > 0:
                previous_block = self.chain[i - 1]
                if current_block.previous_hash != previous_block.compute_hash():
                    self.switch_to_original_chain(fork_index)
                    return False
        if len(self.chain) <= fork_index:
            self.switch_to_original_chain(fork_index)
            return False
        return True

    def switch_to_original_chain(self, fork_index):
        while len(self.chain) > fork_index:
            self.chain.pop()

    def rebuild_utxos(self):
        self.utxos.flushdb()
        for block in self.chain:
            self.update_utxos(block)

    def receive_transaction(self, tx: Transaction):
        # Validate transaction
        input_value = 0
        output_value = sum(output.amount for output in tx.outputs)
        for input in tx.inputs:
            key = f"{input.prev_txid}:{input.vout}"
            utxo_data = self.utxos[key]
            if utxo_data is None:
                return False
            utxo = json.loads(str(self.utxos.get(key)))
            input_value += utxo["amount"]
        if not tx.verify() or input_value < output_value:
            return False
        
        # NOTE: this doesnt add to currently mined blockconsider
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
        total_input_value = 0
        inputs = []
        for key in self.utxos.scan_iter("utxo:*"):
            utxo_data = self.utxos.get(key)
            if utxo_data is not None:
                utxo = json.loads(str(utxo_data))
                if utxo['address'] == sender:
                    total_input_value += utxo['amount']
                    _, prev_txid, vout_str = key.decode('utf-8').split(':')
                    inputs.append(Input(prev_txid, int(vout_str)))
                    if total_input_value >= amount:
                        break
        return (total_input_value, inputs)

    def update_utxos(self, new_block: Block):
        for tx in new_block.transactions:
            # remove spent UTXOs
            for input in tx.inputs:
                key = f"{input.prev_txid}:{input.vout}"
                self.utxos.delete(key)

            # add new outputs
            tx_id = tx.compute_txid()
            for vout, output in enumerate(tx.outputs):
                key = f"{tx_id}:{vout}"
                self.utxos[key] = output

    def get_balance(self, address):
        balance = 0
        for key in self.utxos.scan_iter("utxo:*"):
            utxo_data = self.utxos.get(key)
            if utxo_data is not None:
                utxo = json.loads(str(utxo_data))
                if utxo['address'] == address:
                    balance += utxo['amount']
        return balance

    def create_coinbase_transaction(self, recipient, amount, index):
        outputs = [Output(recipient, amount)]
        tx = Transaction([], outputs, index)
        self.unconfirmed_transactions.insert(0, tx) # first
        return tx

    # Create and add UTXO transaction with inputs, outputs 
    def create_transaction(self, sender, recipient, amount, sender_private_key):
        total_input_value, inputs = self.find_inputs(sender, amount)
        outputs = [Output(recipient, amount)]

        # Insufficient funds
        if total_input_value < amount:
            print(f'Insufficient funds: {total_input_value} instead of {amount}')
            return None

        # Handle returning back to the sender
        change_amount = total_input_value - amount
        if change_amount > 0:
            outputs.append(Output(sender, change_amount))

        # NOTE: potentially handle transaction fees

        transaction = Transaction(inputs, outputs)
        transaction.sign(sender_private_key)
        if transaction.verify():
            self.unconfirmed_transactions.append(transaction)
            self.node.new_transaction(transaction)
            self.storage_manager.store_transaction(transaction)
            return transaction
        return None

    # update uncormined transactions after new block
    def remove_confirmed_transactions(self, confirmed_transactions):
        confirmed_txids = {tx.compute_txid() for tx in confirmed_transactions}
        self.unconfirmed_transactions = [tx for tx in self.unconfirmed_transactions if tx.compute_txid() not in confirmed_txids]

    def mine(self, miner_address):
        last_block = self.chain[-1]
        self.create_coinbase_transaction(miner_address, 1, last_block.index + 1)  # Reward the miner
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
            self.update_utxos(new_block)
            self.remove_confirmed_transactions(new_block.transactions)
            self.node.new_block(new_block) # transmit block to peers
        return new_block.index

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            if current_block.previous_hash != previous_block.compute_hash():
                return False
        return True

    # update difficulty to take 1 minute to mine block
    # decide according to last 20 blocks
    def dynamic_difficulty(self):
        if len(self.chain) > 20:
            actual_time_diff = self.chain[-1].timestamp - self.chain[-21].timestamp
            old_difficulty = self.chain[-1].difficulty
            estimated_time_diff = 1200 # 1 minute

            if actual_time_diff == 0:
                actual_time_diff = 1
            new_difficulty = old_difficulty * estimated_time_diff // actual_time_diff

            return max(new_difficulty, 1)
        return self.difficulty

    def calculate_cumulative_difficulty(self):
        cumulative_difficulty = 0
        for block in self.chain:
            cumulative_difficulty += 2 ** block.difficulty
        return cumulative_difficulty

    def load_blockchain(self):
        chain = self.storage_manager.load_blockchain_data()
        if chain:
            self.chain = chain
        self.unconfirmed_transactions = self.storage_manager.load_all_transactions()

    def quit(self):
        self.node.close()
        self.storage_manager.store_blockchain_data(self) # save to MongoDB
        self.storage_manager.close_connection()

    def latest_block(self):
        if len(self.chain) == 0:
            return None
        return self.chain[-1]

