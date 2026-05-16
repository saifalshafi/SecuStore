"""Blockchain ledger for auditing file operations.

Provides a lightweight, append-only chain of blocks stored in the database.
Each block captures an action (upload, download, delete) along with its
SHA-256 hash and a pointer to the previous block's hash, making tampering
detectable via ``verify_chain``.
"""

import hashlib
import json
from datetime import datetime


def calculate_hash(index, timestamp, action, username, file_name, file_hash, details, previous_hash):
    """Compute the SHA-256 hash for a block's contents.

    Args:
        index (int): Block sequence number.
        timestamp: Block creation timestamp (coerced to str).
        action (str): Action type (e.g. 'upload', 'download', 'delete').
        username (str): Username of the actor.
        file_name (str): Name of the file involved.
        file_hash (str): HMAC or content hash of the file.
        details (str): Additional detail string.
        previous_hash (str): Hash of the preceding block.

    Returns:
        str: Hex-encoded SHA-256 digest.
    """
    data = json.dumps(
        {
            'index': index,
            'timestamp': str(timestamp),
            'action': action,
            'username': username,
            'file_name': file_name,
            'file_hash': file_hash,
            'details': details,
            'previous_hash': previous_hash,
        },
        sort_keys=True,
    )
    return hashlib.sha256(data.encode()).hexdigest()


def get_last_block():
    """Return the most recent ``Block`` record, or ``None`` if the chain is empty."""
    from .models import Block
    return Block.objects.order_by('-index').first()


def create_genesis_block():
    """Create and persist the genesis (first) block for an empty chain.

    Returns:
        Block: The newly created genesis block.
    """
    from .models import Block
    timestamp = datetime.now()
    block_hash = calculate_hash(
        0, timestamp, 'genesis', 'system', '', '', 'Genesis Block', '0' * 64,
    )
    return Block.objects.create(
        index=0,
        action='genesis',
        username='system',
        file_name='',
        file_hash='',
        details='Genesis Block',
        previous_hash='0' * 64,
        block_hash=block_hash,
    )


def add_block(action, username, file_name='', file_hash='', details=''):
    """Append a new block to the chain.

    Creates the genesis block automatically if the chain is empty.

    Args:
        action (str): Action type (e.g. 'upload', 'download', 'delete').
        username (str): Username of the actor.
        file_name (str): Name of the file involved (optional).
        file_hash (str): HMAC or content hash of the file (optional).
        details (str): Additional detail string (optional).

    Returns:
        Block: The newly created block.
    """
    from .models import Block
    last_block = get_last_block()
    if last_block is None:
        last_block = create_genesis_block()

    new_index = last_block.index + 1
    timestamp = datetime.now()
    previous_hash = last_block.block_hash
    block_hash = calculate_hash(
        new_index, timestamp, action, username,
        file_name, file_hash, details, previous_hash,
    )
    return Block.objects.create(
        index=new_index,
        action=action,
        username=username,
        file_name=file_name,
        file_hash=file_hash,
        details=details,
        previous_hash=previous_hash,
        block_hash=block_hash,
    )


def verify_chain():
    """Verify the integrity of the entire blockchain.

    Re-computes the hash for every block and checks that each block's
    ``previous_hash`` matches the hash of the preceding block.

    Returns:
        tuple[bool, str]: ``(is_valid, message)`` where *is_valid* is
        ``True`` only if the chain is intact.
    """
    from .models import Block
    blocks = list(Block.objects.order_by('index'))
    if not blocks:
        return True, "Chain is empty"

    for i, block in enumerate(blocks):
        expected_hash = calculate_hash(
            block.index, block.timestamp, block.action,
            block.username, block.file_name, block.file_hash,
            block.details, block.previous_hash,
        )
        if block.block_hash != expected_hash:
            return False, f"Block #{block.index} tampered!"
        if i > 0 and block.previous_hash != blocks[i - 1].block_hash:
            return False, f"Block #{block.index} chain broken!"

    return True, f"Chain valid - {len(blocks)} blocks verified"
