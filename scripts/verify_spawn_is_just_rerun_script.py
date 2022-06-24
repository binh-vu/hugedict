from multiprocessing.dummy import freeze_support
import os
import multiprocessing as mp


x = 0


def f():
    global x
    print("In process", os.getpid(), "x =", x)


def main():
    global x
    x = 1

    f()

    p = mp.Process(target=f)
    p.start()
    p.join()


if __name__ == "__main__":
    mp.set_start_method("spawn")
    # freeze_support()
    main()
