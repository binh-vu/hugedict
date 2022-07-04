FROM quay.io/pypa/manylinux2014_x86_64:latest

RUN yum install -y llvm-toolset-7
RUN curl --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

ADD ./entrypoint.sh /entrypoint.sh

ENV PATH=${HOME}/.cargo/bin:${PATH}

ENTRYPOINT [ "bash", "/entrypoint.sh" ]