import datetime
import functools
import multiprocessing as mp
import sys
import time
from pprint import pprint
from timeit import Timer

import numpy as np
import pandas as pd
import psutil
import pyarrow as pa


class Timer:
    """A simple object for timing."""

    def __init__(self):
        """Initializing always starts the timer."""
        self.start()

    def start(self):
        """Explicit start method; will clear previous values. Start always happens on initialization."""
        self._start = time.time()
        self._stop = None
        self._past_stops = [self._start]

    def stop(self):
        self._stop = time.time()
        self._past_stops.append(self._stop)

    def clear(self):
        self._stop = None
        self._start = None

    def __call__(self):
        stop = self._stop if self._stop is not None else time.time()
        self._past_stops.append(stop)
        return stop - self._start

    def __str__(self):
        """Reports current time or, if stopped, stopped time."""
        duration = self.__call__()
        return str(datetime.timedelta(seconds=duration))
        # return str(round(duration, 4))

    def delta(self):
        """Return delta from previous calls or __str__ calls. Does not add an additional stop."""
        if len(self._past_stops) > 1:
            return self._past_stops[-1] - self._past_stops[-2]


def run_timer(f):
    """Decorator that times and reports time of a function call"""

    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        print(
            "run_timer: <start>",
            f.__name__,
        )
        t = Timer()

        post = f(*args, **kwargs)

        print(
            "run_timer:  <stop>",
            f.__name__,
            str(t),
        )

        return post

    return wrapped


def get_sample_data_simple(rows):
    data = pd.DataFrame(
        {
            0: [f"sec_{i}" for i in range(rows)],
            1: np.random.rand(rows),
            2: np.array([True if i % 2 == 0 else None for i in range(rows)]),
            **{k: np.random.rand(rows) for k in range(200)},
        }
    )
    return data


def get_sample_data(rows):

    get_bool_array = lambda: np.array(
        [True if i % 2 == 0 else None for i in range(rows)]
    )

    data = pd.DataFrame(
        {
            0: [f"sec_{i}" for i in range(rows)],
            1: np.random.rand(rows),
            2: get_bool_array(),
            **{
                k: (np.random.rand(rows) if k % 2 == 0 else get_bool_array())
                for k in range(200)
            },
        }
    )
    return data


def get_data_arrow(rows):
    data = get_sample_data(rows)
    arrow_data = []
    for column in data:
        arrow_data.append(pa.array(column))
    return arrow_data


def get_numpy_array(rows):
    return get_sample_data(rows)


def get_batch(rows):
    data = get_data_arrow(rows)
    # batch = pa.record_batch(data, names=[f"{x}" for x in range(0, cols)])
    batch = pa.RecordBatch.from_arrays(
        data,
        names=[f"{x}" for x in range(len(data))],
    )
    return batch


def get_sink(table):
    sink = pa.BufferOutputStream()
    writer = pa.ipc.new_stream(sink, table.schema)
    writer.write_batch(table)
    writer.close()
    buf = sink.getvalue()
    return buf


def process_buffer(args):
    buf, index = args
    reader = pa.ipc.open_stream(buf)
    batches = [b for b in reader]
    values = batches[0][index]
    print(values[0])
    # print(values)


def run_with_buffer(buf, rows, cols):
    with mp.Pool(5) as p:
        p.map(process_buffer, [(buf, i) for i in range(cols)])


def process_batch(args):
    batches, index = args
    # df = batches.to_pandas()
    values = batches[0][index]
    # print(values)
    # print(values)
    # x = df[str(index)]
    # print(index, x[0])


def run_with_batch(batch, cols):
    with mp.Pool(5) as p:
        p.map(process_batch, [(batch, i) for i in range(cols)])


# numpy related funcs
def process_with_pandas(args):
    data, index = args
    x = data[index]
    # print(index, x[0])


def run_with_pandas(data, row, cols):
    with mp.Pool(5) as p:
        p.map(process_with_pandas, [(data, i) for i in range(cols)])


if __name__ == "__main__":

    for rows in (
        15000,
        1000000,
        # 100000000,
    ):  # , (10000, 100), (100000, 100), (1000000, 100)):

        df = get_sample_data(rows)
        table = (
            pa.Table.from_pandas(df, preserve_index=False).combine_chunks()
            # .to_batches()
        )

        print(rows, table.nbytes)
        run_timer(run_with_batch)(table, table.num_columns)

        # # data = get_batch(table)
        # buf = get_sink(table)
        # print("run_with_buffer")
        # print(rows, buf.size)  #
        # run_timer(run_with_buffer)(buf, rows, table.num_columns)

        # breakpoint()
        #
        print("run_with_pandas")  #
        print(rows)  #
        run_timer(run_with_pandas)(df, rows, len(df.columns))  #
