#!/usr/bin/env python3
import logging
import threading
import time
import concurrent.futures

def thread_function(name):
    logging.info("Thread %s: starting", name)
    time.sleep(2)
    logging.info("Thread %s: finishing", name)

if __name__ == "__main__":
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    thread1 = threading.Thread(target=thread_function, args=(1,))
    thread2 = threading.Thread(target=thread_function, args=(2,))

    thread1.start()
    print("I waited for the join")
    thread2.start()

