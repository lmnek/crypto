import ecdsa
import json
from typing import List
from functions import *

"""
    Transaction and UTXO scheme implementing P2PKH
"""

class Input:
    
    # In real BTC - use ScriptPubKey instead of storing public key
    def __init__(self, prev_txid, vout) -> None:
        self.prev_txid = prev_txid # previous transaction 
        self.vout = vout # index of an output in the previous transaction
        self.signature = None
        self.public_key = None

    def sign(self, tx_id, private_key_bytes, public_key) -> None:
        sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1) # derive ECDSA private key
        self.signature = sk.sign(tx_id.encode()).hex() # sign the hash of inputs/outputs
        self.public_key = public_key

class Output:
    def __init__(self, address, amount) -> None:
        self.address = address # receiver address 
        self.amount = amount

class Transaction:
    def __init__(self, inputs: List[Input], outputs: List[Output]):
        self.inputs = inputs
        self.outputs = outputs
        self.signature = None

    def compute_txid(self) -> str:
        # without signatures
        tx_data = {
            'inputs': [{'prev_txid': inp.prev_txid, 'vout': inp.vout} for inp in self.inputs],
            'outputs': [{'address': out.address, 'amount': out.amount} for out in self.outputs]
        }
        tx_string = json.dumps(tx_data, sort_keys=True)
        return hashlib.sha256(tx_string.encode()).hexdigest()

    def sign(self, private_key):
        private_key_bytes = bytes.fromhex(private_key)
        public_key = derive_public_key(private_key_bytes).hex()
        tx_id = self.compute_txid()

        for input in self.inputs:
            input.sign(tx_id, private_key_bytes, public_key)


    def verify(self) -> bool:
        tx_id = self.compute_txid()
        # Verify each input
        for input in self.inputs:
            if not input.public_key or not input.signature:
                return False
            vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(input.public_key), curve=ecdsa.SECP256k1)
            if not vk.verify(bytes.fromhex(input.signature), tx_id.encode()):
                return False  
        return True
