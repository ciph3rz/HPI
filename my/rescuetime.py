'''
Rescuetime (phone activity tracking) data.
'''
REQUIRES = [
    'git+https://github.com/karlicoss/rescuexport',
]

from pathlib import Path
from datetime import datetime, timedelta
from typing import Sequence, Iterable

from .core import get_files, LazyLogger
from .core.common import mcachew
from .core.error import Res, split_errors
from .core.pandas import check_dataframe as cdf, DataFrameT

from my.config import rescuetime as config


log = LazyLogger(__package__, level='info')


def inputs() -> Sequence[Path]:
    return get_files(config.export_path)


import rescuexport.dal as dal
DAL = dal.DAL
Entry = dal.Entry


@mcachew(hashf=lambda: inputs())
def entries() -> Iterable[Res[Entry]]:
    dal = DAL(inputs())
    it = dal.entries()
    yield from dal.entries()


def groups(gap: timedelta=timedelta(hours=3)) -> Iterable[Res[Sequence[Entry]]]:
    vit, eit = split_errors(entries(), ET=Exception)
    yield from eit
    import more_itertools
    from more_itertools import split_when
    yield from split_when(vit, lambda a, b: (b.dt - a.dt) > gap)


@cdf
def dataframe() -> DataFrameT:
    import pandas as pd # type: ignore
    # type: ignore[call-arg, attr-defined]
    def it():
        for e in entries():
            if isinstance(e, Exception):
                yield dict(error=str(e))
            else:
                yield e._asdict()
    return pd.DataFrame(it())


from .core import stat, Stats
def stats() -> Stats:
    return {
        **stat(groups),
        **stat(entries),
    }


# basically, hack config and populate it with fake data? fake data generated by DAL, but the rest is handled by this?

from typing import Iterator
from contextlib import contextmanager
# todo take seed, or what?
@contextmanager
def fake_data(rows: int=1000) -> Iterator[None]:
    # todo also disable cachew automatically for such things?
    from .core.cachew import disabled_cachew
    from .core.cfg import override_config
    from tempfile import TemporaryDirectory
    with disabled_cachew(), override_config(config) as cfg, TemporaryDirectory() as td:
        tdir = Path(td)
        cfg.export_path = tdir
        f = tdir / 'rescuetime.json'
        import json
        f.write_text(json.dumps(dal.fake_data_generator(rows=rows)))
        yield
# TODO ok, now it's something that actually could run on CI!
# todo would be kinda nice if doctor could run against the fake data, to have a basic health check of the module?


# todo not sure if I want to keep these here? vvv

def fill_influxdb():
    from influxdb import InfluxDBClient # type: ignore
    client = InfluxDBClient()
    # client.delete_series(database='lastfm', measurement='phone')
    db = 'test'
    client.drop_database(db)
    client.create_database(db)
    # todo handle errors
    vit = (e for e in entries() if isinstance(e, dal.Entry))
    jsons = [{
        "measurement": 'phone',
        "tags": {},
        "time": str(e.dt),
        "fields": {"name": e.activity},
    } for e in vit]
    client.write_points(jsons, database=db) # TODO??

