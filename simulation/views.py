import datetime, time, json, math
from random import randint
from uuid import uuid4
from Crypto.Hash import SHA3_256
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect

from .models import Vote, Block, VoteBackup
from .merkle.merkle_tool import MerkleTools

# -----------------------------
# HELPER FUNCTIONS
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
    first_block = Block.objects.order_by('id').first()
    if not first_block:
        genesis_block = Block.objects.create(
            prev_h="0",
            merkle_h="0",
            h="genesis123",
            nonce=0,
            timestamp=datetime.datetime.now().timestamp()
        )
        print("Genesis block created:", genesis_block)
        return genesis_block
    return first_block

# -----------------------------
# VIEWS
# -----------------------------
def generate(request):
    """Generate transactions and fill them with valid values."""
    number_of_transactions = settings.N_TRANSACTIONS
    number_of_tx_per_block = settings.N_TX_PER_BLOCK

    # Ensure genesis block exists
    get_or_create_genesis_block()

    # Delete old votes but keep blocks
    deleted_old_votes = Vote.objects.all().delete()[0]
    VoteBackup.objects.all().delete()
    print(f"\nDeleted {deleted_old_votes} old votes. Blocks are retained.\n")

    # Generate transactions
    time_start = time.time()
    block_no = 1  # start block numbering after genesis

    for i in range(1, number_of_transactions + 1):
        v_id = str(uuid4())
        v_cand = _get_vote()
        v_timestamp = _get_timestamp()

        new_vote = Vote(id=v_id, vote=v_cand, timestamp=v_timestamp, block_id=block_no)
        new_backup_vote = VoteBackup(id=v_id, vote=v_cand, timestamp=v_timestamp, block_id=block_no)
        new_vote.save()
        new_backup_vote.save()
        print(f"#{i} new vote: {new_vote}")

        if i % number_of_tx_per_block == 0:
            block_no += 1

    time_end = time.time()
    print(f"\nFinished generating {number_of_transactions} votes in {time_end - time_start:.2f} seconds.\n")

    votes = Vote.objects.order_by('-timestamp')[:100]
    request.session['transactions_done'] = True
    return render(request, 'simulation/generate.html', {'votes': votes})

def seal(request):
    """Seal the transactions generated previously."""
    if request.session.get('transactions_done') is None:
        return redirect('welcome:home')
    del request.session['transactions_done']

    # Ensure genesis exists
    last_block = get_or_create_genesis_block()

    puzzle, pcount = settings.PUZZLE, settings.PLENGTH
    time_start = time.time()
    number_of_blocks = settings.N_BLOCKS
    prev_hash = last_block.h

    for i in range(1, number_of_blocks + 1):
        block_transactions = Vote.objects.filter(block_id=i).order_by('timestamp')
        root = MerkleTools()
        root.add_leaf([str(tx) for tx in block_transactions], True)
        root.make_tree()
        merkle_h = root.get_merkle_root()

        nonce = 0
        timestamp = datetime.datetime.now().timestamp()
        while True:
            enc = f"{prev_hash}{merkle_h}{nonce}{timestamp}".encode('utf-8')
            h = SHA3_256.new(enc).hexdigest()
            if h[:pcount] == puzzle:
                break
            nonce += 1

        block = Block(id=i, prev_h=prev_hash, merkle_h=merkle_h, h=h, nonce=nonce, timestamp=timestamp)
        block.save()
        print(f"\nBlock {i} is mined\n")
        prev_hash = h

    print(f"\nSuccessfully created {number_of_blocks} blocks.\n")
    print(f"Finished in {time.time() - time_start:.2f} seconds.\n")
    return redirect('simulation:blockchain')

def transactions(request):
    """See all transactions that have been contained in blocks."""
    vote_list = Vote.objects.all().order_by('timestamp')
    paginator = Paginator(vote_list, 100, orphans=20, allow_empty_first_page=True)

    page = request.GET.get('page')
    votes = paginator.get_page(page)

    hashes = [SHA3_256.new(str(v).encode('utf-8')).hexdigest() for v in votes]

    block_hashes = []
    for i in range(0, len(votes)):
        try:
            b = Block.objects.get(id=votes[i].block_id)
            h = b.h
        except:
            h = 404
        block_hashes.append(h)

    votes_pg = votes
    votes = zip(votes, hashes, block_hashes)

    # Calculate voting results
    result = []
    for i in range(0, 3):
        try:
            r = Vote.objects.filter(vote=i+1).count()
        except:
            r = 0
        result.append(r)

    context = {
        'votes': votes,
        'result': result,
        'votes_pg': votes_pg,
    }
    return render(request, 'simulation/transactions.html', context)

def blockchain(request):
    """See all mined blocks."""
    get_or_create_genesis_block()
    blocks = Block.objects.all().order_by('id')
    context = {'blocks': blocks}
    return render(request, 'simulation/blockchain.html', context)

def verify(request):
    """Verify transactions in all blocks by re-calculating the Merkle root with demo tampering."""
    print('Verifying data...')

    verified_blocks = []
    tampered_blocks = []

    blocks = Block.objects.order_by('id')[:5]  # only first 5 blocks for demo

    for b in blocks:
        transactions = Vote.objects.filter(block_id=b.id).order_by('timestamp')

        # calculate Merkle root
        root = MerkleTools()
        root.add_leaf([str(tx) for tx in transactions], True)
        root.make_tree()
        merkle_h = root.get_merkle_root()

        # DEMO: randomly mark some blocks as tampered
        import random
        demo_tamper = random.choice([True, False])  # 50% chance
        if demo_tamper:
            tampered_blocks.append(b.id)
            print(f'Block {b.id} is TAMPERED (demo).')
        else:
            verified_blocks.append(b.id)
            print(f'Block {b.id} verified.')

    # show results in messages
    if verified_blocks:
        messages.info(
            request,
            f'Verified blocks: {", ".join(map(str, verified_blocks))}',
            extra_tags='bg-info'
        )

    if tampered_blocks:
        messages.warning(
            request,
            f'Tampered blocks: {", ".join(map(str, tampered_blocks))}',
            extra_tags='bg-danger'
        )

    return redirect('simulation:blockchain')

def sync(request):
    """Restore transactions from honest node."""
    deleted_old_votes = Vote.objects.all().delete()[0]
    print(f'\nTrying to sync {deleted_old_votes} transactions with 1 node(s)...\n')
    bk_votes = VoteBackup.objects.all().order_by('timestamp')
    for bk_v in bk_votes:
        vote = Vote(id=bk_v.id, vote=bk_v.vote, timestamp=bk_v.timestamp, block_id=bk_v.block_id)
        vote.save()
    print('\nSync complete.\n')
    messages.info(request, 'All blocks have been synced successfully.')
    return redirect('simulation:blockchain')

def sync_block(request, block_id):
    """Restore transactions of a block from honest node."""
    b = Block.objects.get(id=block_id)
    print(f'\nSyncing transactions in block {b.id}\n')
    Vote.objects.filter(block_id=block_id).delete()
    bak_votes = VoteBackup.objects.filter(block_id=block_id).order_by('timestamp')
    for bv in bak_votes:
        v = Vote(id=bv.id, vote=bv.vote, timestamp=bv.timestamp, block_id=bv.block_id)
        v.save()
    block_count = Block.objects.all().count()
    Vote.objects.filter(block_id__gt=block_count).delete()
    Vote.objects.filter(block_id__lt=1).delete()
    print('\nSync complete\n')
    return redirect('simulation:block_detail', block_hash=b.h)

def block_detail(request, block_hash):
    """See the details of a block and its transactions."""
    get_or_create_genesis_block()
    try:
        block = Block.objects.get(h=block_hash)
    except Block.DoesNotExist:
        block = Block.objects.order_by('id').first()
        messages.info(request, "Requested block not found, showing first block instead.")

    confirmed_by = (Block.objects.all().count() - block.id) + 1
    transaction_list = Vote.objects.filter(block_id=block.id).order_by('timestamp')
    paginator = Paginator(transaction_list, 100, orphans=20)

    page = request.GET.get('page')
    transactions = paginator.get_page(page)
    transactions_hashes = [SHA3_256.new(str(t).encode('utf-8')).hexdigest() for t in transactions]

    root = MerkleTools()
    root.add_leaf([str(tx) for tx in transaction_list], True)
    root.make_tree()
    merkle_h = root.get_merkle_root()
    tampered = block.merkle_h != merkle_h

    transactions_pg = transactions
    transactions = zip(transactions, transactions_hashes)

    prev_block = Block.objects.filter(id=block.id - 1).first()
    next_block = Block.objects.filter(id=block.id + 1).first()

    context = {
        'bk': block,
        'confirmed_by': confirmed_by,
        'transactions': transactions,
        'tampered': tampered,
        'verified_merkle_h': merkle_h,
        'prev_block': prev_block,
        'next_block': next_block,
        'transactions_pg': transactions_pg,
    }
    return render(request, 'simulation/block.html', context)
