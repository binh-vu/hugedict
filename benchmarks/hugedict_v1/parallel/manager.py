from abc import abstractmethod
from loguru import logger
from multiprocessing import shared_memory, resource_tracker
from multiprocessing.managers import BaseManager, SharedMemoryManager
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import Callable, Optional, Union
from hugedict_v1.mrsw_rocksdb import (
    BloomFilterArgs,
    IProxyDict,
    PrimarySyncedRocksDBDict,
)
from hugedict.types import K, V

MB = 1024 * 1024


class MyManager(BaseManager):
    pass


MySharedMemoryManager = SharedMemoryManager


class ISharedMemoryProxyDictServer(IProxyDict):
    @abstractmethod
    def create_shared_memory(self, size: int) -> str:
        pass

    @abstractmethod
    def unlink_shared_memory(self, name: str):
        pass

    @abstractmethod
    def unlink_all_shared_memories(self):
        """Destroy all shared memory it has created."""
        pass

    @abstractmethod
    def raw_indirect_set(self, key: bytes, shared_mem_name: str, value_size: int):
        pass


class SharedMemoryDictClient(IProxyDict):
    """A client that interaction with the real proxy dict via shared memory.

    Note that we must delay creating the shared memory until the first time we actually
    need to use it to ensure that the shared memory is not appeared in the resource
    tracker process of the server. This is because of the current problematic implementation
    of shared memory in python that a shared memory is tracked twice (please see: https://bugs.python.org/issue39959).
    """

    def __init__(
        self,
        server: ISharedMemoryProxyDictServer,
        min_increase_size: int = int(1 * MB),
    ):
        self.server = server
        self.shared_mem = None
        self.min_increase_size = min_increase_size

    def __del__(self):
        if self.shared_mem is not None:
            self.shared_mem.close()
            self.server.unlink_shared_memory(self.shared_mem.name)

    def raw_set(self, key: bytes, value: bytes):
        # save data to shared memory
        value_size = len(value)
        if self.shared_mem is None or self.shared_mem.size < value_size:
            new_size = max(
                round(value_size / self.min_increase_size) * self.min_increase_size,
                self.min_increase_size,
            )
            if self.shared_mem is not None:
                self.shared_mem.close()
                self.server.unlink_shared_memory(self.shared_mem.name)
            self.shared_mem = SharedMemory(
                name=self.server.create_shared_memory(new_size), create=False
            )
            # resource tracker register shared memory twice - unregister to avoid warnings
            # see more: (the first one is related to our problem but declared as duplicated as the one below)
            # + https://bugs.python.org/issue39959
            # + https://bugs.python.org/issue38119
            resource_tracker.unregister(self.shared_mem._name, "shared_memory")  # type: ignore

        self.shared_mem.buf[:value_size] = value
        self.server.raw_indirect_set(key, str(self.shared_mem.name), value_size)

    def raw_has(self, key: bytes) -> bool:
        return self.server.raw_has(key)

    def raw_get(self, key: bytes) -> Optional[bytes]:
        return self.server.raw_get(key)


class SharedMemoryPrimarySyncedRocksDBDict(
    PrimarySyncedRocksDBDict[K, V], ISharedMemoryProxyDictServer
):
    def __init__(
        self,
        dbpath: Union[Path, str],
        create_if_missing=False,
        deser_key: Callable[[bytes], K] = None,
        deser_value: Callable[[bytes], V] = None,
        ser_key: Callable[[K], bytes] = None,
        ser_value: Callable[[V], bytes] = None,
        bloomfilter_args: BloomFilterArgs = None,
        enable_bloomfilter: bool = True,
    ):
        super().__init__(
            dbpath,
            create_if_missing,
            deser_key,
            deser_value,
            ser_key,
            ser_value,
            bloomfilter_args,
            enable_bloomfilter,
        )

        self.shared_mems = {}

    def create_shared_memory(self, size: int) -> str:
        sm = SharedMemory(create=True, size=size)
        self.shared_mems[sm.name] = sm
        return sm.name

    def unlink_shared_memory(self, name: str):
        self.shared_mems[name].unlink()
        del self.shared_mems[name]

    def unlink_all_shared_memories(self):
        names = list(self.shared_mems.keys())
        for name in names:
            self.unlink_shared_memory(name)

    def raw_indirect_set(self, key: bytes, shared_mem_name: str, value_size: int):
        value = self.shared_mems[shared_mem_name].buf[:value_size]
        self.raw_set(key, bytes(value))


MyManager.register("PrimarySyncedRocksDBDict", PrimarySyncedRocksDBDict)
MyManager.register(
    "SharedMemoryPrimarySyncedRocksDBDict", SharedMemoryPrimarySyncedRocksDBDict
)
