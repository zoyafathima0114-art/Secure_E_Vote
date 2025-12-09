import os
import django
import datetime
import time
from uuid import uuid4
from random import randint
from Crypto.Hash import SHA3_256

# -----------------------------
# Setup Django environment
# -----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bbevoting_project.settings")
django.setup()

from simulation.models import Vote, VoteBackup, Block
from simulation.merkle.merkle_tool import MerkleTools
from django.conf import settings

# -----------------------------
# Helper functions
# -----------------------------
def _get_vote():
    return randint(1, 3)

def _get_timestamp():
    return datetime.datetime.now().timestamp()

def get_or_create_genesis_block():
    """
    Ensure at least one block exists.
    If none exists, create the genesis block.
    """
    if not Block.objects.exists():
        genesis_block = Block.objects.create(
            prev_h="0",
            merkle_h="0",
            h="genesis123",
            nonce=0,
            timestamp=datetime.datetime.now().timestamp()
        )
        print("✅ Genesis block created:", genesis_block)
        return genesis_block
    print("✅ Genesis block already exists")
    return Block.objects.first()

# -----------------------------
# Main script
# -----------------------------
if __name__ == "__main__":
    print("✅ Make sure you already ran 'python manage.py migrate'")
    
    # Create genesis block if missing
    get_or_create_genesis_block()
    
    # Clear old votes and backups
    deleted_votes = Vote.objects.all().delete()[0]
    VoteBackup.objects.all().delete()
    print(f"🗑 Cleared old votes and backups ({deleted_votes} deleted)")

    # -----------------------------
    # Generate transactions
    # -----------------------------
    number_of_transactions = getattr(settings, "N_TRANSACTIONS", 50)
    number_of_tx_per_block = getattr(settings, "N_TX_PER_BLOCK", 5)

    block_no = 1
    start_time = time.time()
    for i in range(1, number_of_transactions + 1):
        v_id = str(uuid4())
        v_cand = _get_vote()
        v_timestamp = _get_timestamp()

        new_vote = Vote(id=v_id, vote=v_cand, timestamp=v_timestamp, block_id=block_no)
        new_backup_vote = VoteBackup(id=v_id, vote=v_cand, timestamp=v_timestamp, block_id=block_no)
        new_vote.save()
        new_backup_vote.save()

        print(f"# {i} new vote: {new_vote}")

        if i % number_of_tx_per_block == 0:
            block_no += 1

    print(f"\nFinished generating {number_of_transactions} votes in {time.time() - start_time:.2f} seconds.\n")

    # -----------------------------
    # Seal blocks
    # -----------------------------
    print("🔐 Mining blocks...")

    puzzle = getattr(settings, "PUZZLE", "0")
    pcount = getattr(settings, "PLENGTH", 1)
    prev_hash = Block.objects.order_by("id").last().h

    number_of_blocks = getattr(settings, "N_BLOCKS", block_no)
    start_time = time.time()

    for i in range(1, number_of_blocks + 1):
        block_transactions = Vote.objects.filter(block_id=i).order_by("timestamp")
        if not block_transactions:
            continue

        # Build Merkle root
        mt = MerkleTools()
        mt.add_leaf([str(tx) for tx in block_transactions], True)
        mt.make_tree()
        merkle_h = mt.get_merkle_root()

        # Proof of Work
        nonce = 0
        timestamp = datetime.datetime.now().timestamp()
        while True:
            enc = f"{prev_hash}{merkle_h}{nonce}{timestamp}".encode("utf-8")
            h = SHA3_256.new(enc).hexdigest()
            if h[:pcount] == puzzle:
                break
            nonce += 1

        # Save block
        block = Block(id=i, prev_h=prev_hash, merkle_h=merkle_h, h=h, nonce=nonce, timestamp=timestamp)
        block.save()
        print(f"✅ Block {i} mined with hash {h[:16]}...")

        prev_hash = h

    print(f"\n🎉 Successfully mined {number_of_blocks} blocks in {time.time() - start_time:.2f} seconds.")
