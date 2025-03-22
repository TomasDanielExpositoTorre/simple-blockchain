from multiprocessing import Process
from slave import SlaveNode

if __name__ == "__main__":
    num_slaves = 100

    processes = []
    for i in range(num_slaves):
        slave = SlaveNode('localhost', 65432)
        process = Process(target=slave.run)
        process.start()
        processes.append(process)

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("Shutting down all slaves...")
        for process in processes:
            process.terminate()
        
        print("All done.")