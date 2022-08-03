FROM quay.io/pypa/manylinux2014_x86_64:latest

RUN yum install -y llvm-toolset-7

# add a user 1000:1000 so we can build inside the same project
RUN adduser builder && usermod -aG wheel builder

USER builder

RUN curl --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

ADD ./entrypoint.sh /entrypoint.sh

ENV PATH=${HOME}/.cargo/bin:${PATH}

ENTRYPOINT [ "bash", "/entrypoint.sh" ]