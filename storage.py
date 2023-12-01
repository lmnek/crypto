# storage.py
from pymongo import MongoClient
import redis
import time
from itertools import islice
from transaction import Input, Output, Transaction
from blockchain import *
from bson import ObjectId
import json

MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DB_NAME = "blockchain_db"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

class StorageManager:
    def __init__(self):
        # Initialize MongoDB client
        self.mongo_client = MongoClient(MONGODB_URI)
        self.mongo_db = self.mongo_client[MONGODB_DB_NAME]
        
        self.transactions_collection = self.mongo_db.transactions
        self.blockchain_collection = self.mongo_db.blockchain_data
        
        # Initialize Redis client
        self.redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    def store_transaction(self, transaction):
        transaction_data = transaction.serialize()
        self.transactions_collection.insert_one(transaction_data)

    def load_transaction(self, transaction_id):
        result = self.transactions_collection.find_one({"_id": transaction_id})
        if result:
            return Transaction.deserialize(result)
        return None
    
    def load_all_transactions(self):
        all_transactions = []
        cursor = self.transactions_collection.find({})
        for document in cursor:
            inputs_data = document.get("inputs", [])
            outputs_data = document.get("outputs", [])

            # Deserialize inputs
            inputs = [Input(inp["prev_txid"], inp["vout"]) for inp in inputs_data]
            for i, inp in enumerate(inputs):
                inp.signature = inputs_data[i].get("signature")
                inp.public_key = inputs_data[i].get("public_key")

            # Deserialize outputs
            outputs = [Output(out["address"], out["amount"]) for out in outputs_data]

            # Create a Transaction object
            transaction = Transaction(inputs, outputs)
            transaction.signature = document.get("signature")

            all_transactions.append(transaction)

        return all_transactions
    
    def store_transaction(self, transaction):
        # Serialize inputs
        inputs_data = [{"prev_txid": inp.prev_txid, "vout": inp.vout, "signature": inp.signature, "public_key": inp.public_key} for inp in transaction.inputs]

        # Serialize outputs
        outputs_data = [{"address": out.address, "amount": out.amount} for out in transaction.outputs]

        # Serialize the whole transaction
        transaction_data = {
            "inputs": inputs_data,
            "outputs": outputs_data,
            "signature": transaction.signature
        }

        # Store or update in MongoDB
        self.transactions_collection.insert_one(transaction_data)
        print("Transaction stored successfully.")
    def store_blockchain_data(self, blockchain):
        blockchain_data = {"chain": []}

        # Store the genesis block
        genesis_block = blockchain.chain[0]
        genesis_block_data = {
            "index": genesis_block.index,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(genesis_block.timestamp)),
            "data": "Genesis block of simple chain",
            "previousHash": genesis_block.previous_hash,
            "merkleRoot": genesis_block.merkle_root,
            "hash": genesis_block.compute_hash(),
            "difficulty": genesis_block.difficulty,
            "nonce": genesis_block.nonce,
        }
        blockchain_data["chain"].append(genesis_block_data)

        # Store subsequent blocks
        for block in islice(blockchain.chain, 1, None):
            block_data = {
                "index": block.index,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(block.timestamp)),
                "data": [{"inputs": inp, "outputs": outp} for inp, outp in zip(block.transactions[0].inputs, block.transactions[0].outputs)] if block.transactions else "Genesis block of simple chain",
                "previousHash": block.previous_hash,
                "merkleRoot": block.merkle_root,
                "hash": block.compute_hash(),
                "difficulty": block.difficulty,
                "nonce": block.nonce,
            }
            blockchain_data["chain"].append(block_data)

        #debugging output
        #print("Blockchain data to be stored:")
        #print(json.dumps(blockchain_data, indent=2))

        # Store or update in MongoDB
        self.blockchain_collection.update_one({}, {"$set": blockchain_data}, upsert=True)
        print("Blockchain data stored successfully.")

    def load_blockchain_data(self):
        result = self.mongo_db.blockchain_data.find_one({})
        if result:
            chain_data = result["chain"]
            blockchain = Blockchain() 

            for block_data in chain_data:
                index = block_data["index"]
                timestamp = time.mktime(time.strptime(block_data["timestamp"], "%Y-%m-%d %H:%M:%S"))
                previous_hash = block_data["previousHash"]
                nonce = block_data["nonce"]
                difficulty = block_data["difficulty"]

                # Reconstruct transactions from the stored data
                transactions_data = block_data["data"]
                transactions = []
                for transaction_data in transactions_data:
                    inputs = transaction_data["inputs"]
                    outputs = transaction_data["outputs"]
                    transaction = Transaction(inputs, outputs)
                    transactions.append(transaction)

                # Create the block and add it to the blockchain
                block = Block(index, previous_hash, transactions, timestamp, nonce, difficulty)
                blockchain.chain.append(block)

            return blockchain
        else:
            return None  # Or whatever makes sense for your application
           
    def close_connection(self):
        self.mongo_client.close()

    def store_latest_states_in_memory(self, key, value):
        self.redis_client.set(key, value)

    def load_latest_states_from_memory(self, key):
        return self.redis_client.get(key)
    
    def print_blockchain_data(self, limit=None):
        cursor = self.blockchain_collection.find({}).limit(limit)
        for document in cursor:
            print("Blockchain data from database:")
            # Remove the _id field
            if '_id' in document:
                del document['_id']
            # Convert the document to a JSON string
            json_document = json.dumps(document, indent=2)
            print(json_document)

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)