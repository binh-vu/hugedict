FROM manylinux2014_x86_64:latest

RUN yum install -y llvm-toolset-7 && scl enable llvm-toolset-7 bash
RUN curl --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

ENV PATH=${HOME}/.cargo/bin:${PATH}