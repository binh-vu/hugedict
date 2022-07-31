use std::{thread::sleep, time::Duration};

use crate::error::HugeDictError;

use super::{
    dict::{pydeser_value, pyser_key},
    options::Options as DBOptions,
};
use anyhow::Result;
use nng::{
    options::{Options, RecvTimeout},
    *,
};
use pyo3::{
    exceptions::{PyInterruptedError, PyKeyError},
    ffi::PyErr_CheckSignals,
    prelude::*,
    types::{PyBytes, PyTuple},
};

const CHECK_SIGNALS_INTERVAL: Duration = Duration::from_millis(100);
const DIAL_RETRY_INTERVAL: Duration = Duration::from_millis(50);
const DIAL_MAX_RETRIES: usize = 200; // ten seconds

#[derive(Debug)]
pub enum ReqMsg<'s> {
    // stop
    Stop,

    // Write a key-value pair to the database
    Put(&'s [u8], &'s [u8]),

    // Get a key from the database
    Get(&'s [u8]),

    // Check if a key exists in the database
    Contains(&'s [u8]),
}

#[derive(Debug)]
pub enum RepMsg<'s> {
    Error,
    SuccessStop,
    SuccessPut,
    // contains value, empty if there is no value
    SuccessGet(&'s [u8]),
    // whether the key exists
    SuccessContains(bool),
}

impl<'s> RepMsg<'s> {
    pub fn deserialize(buf: &'s [u8]) -> Result<Self> {
        match buf[0] {
            0 => Ok(Self::Error),
            1 => Ok(Self::SuccessStop),
            2 => Ok(Self::SuccessPut),
            3 => Ok(Self::SuccessGet(&buf[1..])),
            4 => Ok(Self::SuccessContains(buf[1] == 1)),
            _ => Err(HugeDictError::IPCImplError(
                "Invalid message. Please report the bug.".to_owned(),
            )
            .into()),
        }
    }

    pub fn serialize(&self) -> Vec<u8> {
        match self {
            Self::Error => vec![0],
            Self::SuccessStop => vec![1],
            Self::SuccessPut => vec![2],
            Self::SuccessGet(value) => {
                let mut buf = Vec::with_capacity(value.len() + 1);
                buf.push(3);
                buf.extend_from_slice(value);
                buf
            }
            Self::SuccessContains(value) => vec![4, *value as u8],
        }
    }
}

impl<'s> ReqMsg<'s> {
    pub fn deserialize(buf: &'s [u8]) -> Result<Self> {
        match buf[0] {
            0 => Ok(Self::Stop),
            1 => {
                let keysize = u64::from_le_bytes(buf[1..9].try_into()?);
                let offset = 9 + keysize as usize;
                Ok(Self::Put(&buf[9..offset], &buf[offset..]))
            }
            2 => Ok(Self::Get(&buf[1..])),
            3 => Ok(Self::Contains(&buf[1..])),
            _ => Err(HugeDictError::IPCImplError(
                "Invalid message. Please report the bug.".to_owned(),
            )
            .into()),
        }
    }

    pub fn serialize(&self) -> Vec<u8> {
        match self {
            Self::Stop => vec![0],
            Self::Put(key, value) => {
                let mut buf = Vec::with_capacity(key.len() + value.len() + 9);
                buf.push(1);
                buf.extend_from_slice(&(key.len() as u64).to_le_bytes());
                buf.extend_from_slice(key);
                buf.extend_from_slice(value);
                buf
            }
            Self::Get(key) => {
                let mut buf = Vec::with_capacity(key.len() + 1);
                buf.push(2);
                buf.extend_from_slice(key);
                return buf;
            }
            Self::Contains(key) => {
                let mut buf = Vec::with_capacity(key.len() + 1);
                buf.push(3);
                buf.extend_from_slice(key);
                return buf;
            }
        }
    }
}

/// Start a primary instance of rocksdb that is responsible
/// for writing records to the database.
#[pyfunction]
pub fn primary_db(url: &str, path: &str, options: &DBOptions) -> Result<()> {
    let db = rocksdb::DB::open(&options.get_options(), path)?;

    let socket = Socket::new(Protocol::Rep0)?;
    socket.listen(url)?;
    socket.set_opt::<RecvTimeout>(Some(CHECK_SIGNALS_INTERVAL))?;

    loop {
        let mut nnmsg = loop {
            if let Ok(m) = socket.recv() {
                break m;
            }

            match socket.recv() {
                Ok(m) => break m,
                Err(Error::TimedOut) => {
                    let signal = unsafe { PyErr_CheckSignals() };
                    if signal != 0 {
                        // users send a signal, perhaps to stop the process.
                        return Err(HugeDictError::PyErr(PyInterruptedError::new_err(
                            "Receiving an incoming signal",
                        ))
                        .into());
                    }
                }
                Err(e) => return Err(HugeDictError::NNGError(e).into()),
            }
        };
        let msg = ReqMsg::deserialize(nnmsg.as_slice())?;

        let rep = match &msg {
            ReqMsg::Stop => {
                nnmsg.clear();
                nnmsg.push_back(&RepMsg::SuccessStop.serialize());
                socket.send(nnmsg).map_err(from_nngerror)?;
                return Ok(());
            }
            ReqMsg::Put(key, value) => {
                db.put(key, value)?;
                RepMsg::SuccessPut.serialize()
            }
            ReqMsg::Get(key) => match db.get_pinned(key)? {
                None => RepMsg::SuccessGet(&[]).serialize(),
                Some(value) => RepMsg::SuccessGet(value.as_ref()).serialize(),
            },
            ReqMsg::Contains(key) => {
                let msg = match db.get_pinned(key)? {
                    None => RepMsg::SuccessContains(false),
                    Some(_) => RepMsg::SuccessContains(true),
                };
                msg.serialize()
            }
        };

        nnmsg.clear();
        nnmsg.push_back(&rep);
        socket.send(nnmsg).map_err(from_nngerror)?;
    }
}

#[pyfunction]
pub fn stop_primary_db(url: &str) -> Result<()> {
    let socket = dial(url)?;
    socket
        .send(&ReqMsg::Stop.serialize())
        .map_err(from_nngerror)?;

    let msg = socket.recv()?;
    match RepMsg::deserialize(&msg)? {
        RepMsg::Error => {
            Err(HugeDictError::IPCImplError("PrimaryDB encounters an error".to_owned()).into())
        }
        RepMsg::SuccessStop => Ok(()),
        _ => Err(
            HugeDictError::IPCImplError("Invalid message. Please report the bug.".to_owned())
                .into(),
        ),
    }
}

/// A secondary instance of rocksdb that will communicate with the primary
/// instance to write records to the database.
#[pyclass(module = "hugedict.hugedict.rocksdb")]
pub struct SecondaryDB {
    db: rocksdb::DB,
    socket: Socket,
    deser_value: Py<PyAny>,
    ser_value: Py<PyAny>,
}

#[pymethods]
impl SecondaryDB {
    #[new]
    pub fn new(
        url: &str,
        primary_path: &str,
        secondary_path: &str,
        options: &DBOptions,
        deser_value: Py<PyAny>,
        ser_value: Py<PyAny>,
    ) -> Result<Self> {
        let socket = dial(url)?;
        let db =
            rocksdb::DB::open_as_secondary(&options.get_options(), primary_path, secondary_path)?;
        Ok(Self {
            db,
            socket,
            deser_value,
            ser_value,
        })
    }

    fn __getitem__(&self, py: Python, key: &PyAny) -> Result<Py<PyAny>> {
        let k0 = pyser_key(key)?;
        let k: &[u8] = k0.as_ref().as_ref();
        match self.db.get_pinned(k)? {
            Some(value) => Ok(pydeser_value(value, &self.deser_value, py)?),
            None => {
                // check if key is in the primary
                self.socket
                    .send(&ReqMsg::Get(k).serialize())
                    .map_err(from_nngerror)?;

                let msg = self.socket.recv()?;
                match RepMsg::deserialize(&msg)? {
                    RepMsg::Error => Err(HugeDictError::IPCImplError(
                        "PrimaryDB encounters an error".to_owned(),
                    )
                    .into()),
                    RepMsg::SuccessGet(data) => {
                        if data.len() == 0 {
                            // key does not exist in the primary
                            Err(PyKeyError::new_err(format!("Key not found: {}", key)).into())
                        } else {
                            Ok(pydeser_value(data, &self.deser_value, py)?)
                        }
                    }
                    _ => Err(HugeDictError::IPCImplError(
                        "Invalid message. Please report the bug.".to_owned(),
                    )
                    .into()),
                }
            }
        }
    }

    fn __setitem__(&self, py: Python, key: &PyAny, value: &PyAny) -> Result<()> {
        let k0 = pyser_key(key)?;
        let k: &[u8] = k0.as_ref().as_ref();

        // send the request to the primary to save
        let v = self.ser_value.call1(py, PyTuple::new(py, [value]))?;
        let vb = v
            .as_ref(py)
            .downcast::<PyBytes>()
            .map_err(|err| PyErr::from(err))?
            .as_bytes();

        self.socket
            .send(&ReqMsg::Put(k, vb).serialize())
            .map_err(from_nngerror)?;

        let msg = self.socket.recv()?;
        match RepMsg::deserialize(&msg)? {
            RepMsg::Error => {
                Err(HugeDictError::IPCImplError("PrimaryDB encounters an error".to_owned()).into())
            }
            RepMsg::SuccessPut => Ok(()),
            _ => Err(HugeDictError::IPCImplError(
                "Invalid message. Please report the bug.".to_owned(),
            )
            .into()),
        }
    }

    fn __contains__(&self, key: &PyAny) -> Result<bool> {
        let k0 = pyser_key(key)?;
        let k: &[u8] = k0.as_ref().as_ref();

        match self.db.get_pinned(k)? {
            Some(_) => Ok(true),
            None => {
                self.socket
                    .send(&ReqMsg::Contains(k).serialize())
                    .map_err(from_nngerror)?;

                let msg = self.socket.recv()?;
                match RepMsg::deserialize(&msg)? {
                    RepMsg::Error => Err(HugeDictError::IPCImplError(
                        "PrimaryDB encounters an error".to_owned(),
                    )
                    .into()),
                    RepMsg::SuccessContains(b) => Ok(b),
                    _ => Err(HugeDictError::IPCImplError(
                        "Invalid message. Please report the bug.".to_owned(),
                    )
                    .into()),
                }
            }
        }
    }
}

#[inline]
pub fn from_nngerror(err: (Message, Error)) -> HugeDictError {
    HugeDictError::NNGError(err.1)
}

#[inline]
pub fn dial(url: &str) -> Result<Socket> {
    let socket = Socket::new(Protocol::Req0)?;

    for _ in 0..DIAL_MAX_RETRIES {
        match socket.dial(url) {
            Ok(_) => return Ok(socket),
            Err(Error::ConnectionRefused) => {
                sleep(DIAL_RETRY_INTERVAL);
            }
            Err(err) => return Err(HugeDictError::NNGError(err).into()),
        }
    }

    return Err(HugeDictError::NNGError(Error::ConnectionRefused).into());
}
