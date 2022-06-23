"""Loading big files into RocksDB
"""
import time
import bz2
from dataclasses import dataclass
import gzip
from math import ceil
import os
from pathlib import Path
import orjson
from rocksdb import DB, WriteBatch  # type: ignore
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple, Union, cast
from multiprocessing.managers import SharedMemoryManager, SyncManager
from multiprocessing.shared_memory import SharedMemory, ShareableList
from multiprocessing import Lock, Pool, Queue, Process
from tqdm import tqdm


class FileFormat(str, Enum):
    # each line is a json list of two items, key is extracted from the first item while value is extracted from the second item
    tuple2 = "tuple2"
    # each line is a json object, key and value are extracted from the object
    jsonline = "jsonline"
    # tab separated format, raw key and value must not contain tab and newline characters such as \r\n.
    tabsep = "tabsep"


@dataclass
class FileReaderArgs:
    infile: Path
    format: FileFormat
    key_fn: Callable[[Any], bytes]
    value_fn: Callable[[Any], bytes]
    shm_pool: List[SharedMemory]
    shm_reserved: ShareableList


def init_pool(l):
    global lock
    lock = l


def load_single_file(
    db: DB,
    infile: Union[str, Path],
    format: FileFormat,
    key_fn: Callable[[Any], bytes],
    value_fn: Callable[[Any], bytes],
    verbose: bool = True,
):
    args = FileReaderArgs(
        infile=Path(infile),
        format=format,
        key_fn=key_fn,
        value_fn=value_fn,
        shm_pool=[],
        shm_reserved=None,  # type: ignore
    )
    lst = read_file(args)
    batch_size = 100000

    wb = WriteBatch()
    for k, v in tqdm(lst, desc="writing", disable=not verbose):
        wb.put(k, v)
        if wb.count() >= batch_size:
            db.write(wb, disable_wal=True)
            wb = WriteBatch()
    if wb.count() > 0:
        db.write(wb, disable_wal=True)
    return db


def load(
    db: DB,
    infiles: Union[List[str], List[Path], List[Union[str, Path]]],
    format: FileFormat,
    key_fn: Callable[[Any], bytes],
    value_fn: Callable[[Any], bytes],
    n_processes: Optional[int] = None,
    shm_mem_limit_mb: int = 128,
    shm_mem_ratio: int = 4,
    verbose: bool = True,
):
    """Load files into rocksdb database"""
    infiles = sorted(infiles)
    if n_processes is None:
        n_cpus = os.cpu_count()
        if n_cpus is None:
            raise Exception("Cannot determine number of CPUs")
        n_processes = min(min(4, n_cpus - 4), n_cpus)

    with cast(Any, SharedMemoryManager()) as smm, tqdm(
        desc="loading", total=len(infiles), disable=not verbose
    ) as pbar:
        n_shared_mems = min(ceil(n_processes * shm_mem_ratio), len(infiles))
        shm_pool = [
            smm.SharedMemory(1024 * 1024 * shm_mem_limit_mb)
            for _ in range(n_shared_mems)
        ]
        shm_reserved = smm.ShareableList([False for _ in range(n_shared_mems)])
        lock = Lock()
        with Pool(
            processes=n_processes, initializer=init_pool, initargs=(lock,)
        ) as pool:
            inputs = [
                FileReaderArgs(
                    infile=Path(infile),
                    format=format,
                    key_fn=key_fn,
                    value_fn=value_fn,
                    shm_pool=shm_pool,
                    shm_reserved=shm_reserved,
                )
                for infile in infiles
            ]
            n_records = 0
            for shm_index in pool.imap_unordered(process_fn, inputs):
                if not shm_reserved[shm_index]:
                    raise Exception(f"Shared memory {shm_index} not reserved")

                pbar.update(1)
                # read and release shared memory
                shm = shm_pool[shm_index]
                # output = read_from_shm(shm)
                pbar.set_postfix(records=n_records, msg="reading batch to db")
                wb = read_from_shm_writebatch(shm)
                lock.acquire()
                try:
                    shm_reserved[shm_index] = False
                finally:
                    lock.release()

                n_records += wb.count()
                # wb = WriteBatch()
                # for k, v in output:
                #     wb.put(k, v)
                #     n_records += 1
                #     pbar.set_postfix(records=n_records, msg="creating batch")

                pbar.set_postfix(records=n_records, msg="writing batch to db")
                db.write(wb, disable_wal=True)
                pbar.set_postfix(records=n_records, msg="wrote batch to db")

    return db


def process_fn(args: FileReaderArgs) -> int:
    """Read file and write list of key-value pairs to shared memory"""
    global lock
    outputs = read_file(args)

    shm_idx = None
    # wait for max 10 minutes for shared memory to be available
    for j in range(600):
        for i in range(len(args.shm_pool)):
            if args.shm_reserved[i]:
                continue

            lock.acquire()
            try:
                if not args.shm_reserved[i]:
                    args.shm_reserved[i] = True
                else:
                    continue
            finally:
                lock.release()
            shm_idx = i
            break
        if shm_idx is None:
            time.sleep(1)
        else:
            break

    if shm_idx is None:
        raise Exception("No shared memory available")

    # write_to_shm(args.shm_pool[shm_idx], outputs)
    write_to_shm_writebatch(args.shm_pool[shm_idx], outputs)
    return shm_idx


def read_file(args: FileReaderArgs) -> List[Tuple[bytes, bytes]]:
    if args.infile.name.endswith(".gz"):
        open_fn = gzip.open
    elif args.infile.name.endswith(".bz2"):
        open_fn = bz2.open
    else:
        open_fn = open

    with open_fn(str(args.infile), "rb") as f:
        key = args.key_fn
        value = args.value_fn
        outputs = []
        if args.format == FileFormat.jsonline:
            for line in f:
                r = orjson.loads(line)
                outputs.append((key(r), value(r)))
        elif args.format == FileFormat.tuple2:
            for line in f:
                k, v = orjson.loads(line)
                outputs.append((key(k), value(v)))
        elif args.format == FileFormat.tabsep:
            for line in f:
                k, v = line.rstrip(b"\r\n").split(b"\t", 1)
                outputs.append((key(k), value(v)))
        else:
            raise Exception(f"Unknown format: {format}")
    return outputs


def write_to_shm_writebatch(shm: SharedMemory, lst: List[Tuple[bytes, bytes]]):
    wb = WriteBatch()
    for k, v in lst:
        wb.put(k, v)
    content = wb.data()
    size = len(content)
    if shm.size < size:
        raise Exception(f"Shared memory too small: {shm.size} < {size}")
    shm.buf[:4] = size.to_bytes(4, "little")
    shm.buf[4 : 4 + size] = content


def read_from_shm_writebatch(shm: SharedMemory) -> WriteBatch:
    size = int.from_bytes(shm.buf[:4], "little")
    return WriteBatch(bytes(shm.buf[4 : 4 + size]))


def write_to_shm(shm: SharedMemory, lst: List[Tuple[bytes, bytes]]):
    n_items = len(lst) * 2
    size = 4 * n_items + sum(len(k) + len(v) for k, v in lst) + 4
    if shm.size < size:
        raise Exception(f"Shared memory too small: {shm.size} < {size}")
    shm.buf[:4] = n_items.to_bytes(4, "little")
    i = 4
    for slst in lst:
        for item in slst:
            shm.buf[i : i + 4] = len(item).to_bytes(4, "little")
            shm.buf[i + 4 : i + 4 + len(item)] = item
            i += len(item) + 4


def read_from_shm(shm: SharedMemory) -> List[Tuple[bytes, bytes]]:
    lst = []
    n_items = int.from_bytes(shm.buf[:4], "little")
    i = 4
    for _ in range(n_items):
        size = int.from_bytes(shm.buf[i : i + 4], "little")
        k = bytes(shm.buf[i + 4 : i + 4 + size])
        i += size + 4

        size = int.from_bytes(shm.buf[i : i + 4], "little")
        v = bytes(shm.buf[i + 4 : i + 4 + size])
        i += size + 4

        lst.append((k, v))
    return lst
