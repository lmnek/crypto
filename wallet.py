from blockchain import *

class Wallet:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.addresses = []

    def create_address(self):
        private_key, address = generate_address()
        self.addresses.append((private_key, address))
        print(f'New address created: {address}')
        return private_key, address

    def get_balance(self, address):
        return self.blockchain.get_balance(address)

    def get_utxos(self, address):
        return [u for u in self.blockchain.utxos.values() if u.address == address]

    def transfer(self, sender_address, recipient_address, amount):
        # Find the private key for the sender address
        for private_key, address in self.addresses:
            if address == sender_address:
                return self.blockchain.create_transaction(sender_address, recipient_address, amount, private_key)
        print(f'Address not found in wallet: {sender_address}')
        return None

    def print_addresses(self):
        for _, address in self.addresses:
            print(address)

    def check_balance(self):
        total_balance = 0
        for _, address in self.addresses:
            balance = self.get_balance(address)
            total_balance += balance
            print(f'Address: {address}, Balance: {balance}')
        print(f'Total balance of the wallet: {total_balance}')

    def print_utxos(self):
        for _, address in self.addresses:
            utxos = self.get_utxos(address)
            utxos_info = [
                {
                    'tx_id': key[0],
                    'vout': key[1],
                    'address': u.address,
                    'amount': u.amount
                }
            for key, u in utxos]
            print(f'UTXOs for address {address}:')
            print(json.dumps(utxos_info, indent=2))
