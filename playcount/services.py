import os
import csv
import tempfile
import shutil
from datetime import datetime
from redis import Redis
from rq import Queue
from dask import dataframe as dd
from playcount.utils import move_file_to_media_dir


class BackgroundService(object):
    """
    """

    def __init__(self) -> None:
        self.q = Queue(connection=Redis())

    def create_new(self, func, args):
        one_day = 86400  # one day in second
        job = self.q.enqueue(func, args=args, result_ttl=one_day)
        return job.id

    def get_job(self, job_id):
        return self.q.fetch_job(job_id)


class CSVService(object):
    """
    """

    def __get_outfile_writer(self):
        handle, file_path = tempfile.mkstemp(suffix='.csv')
        file = os.fdopen(handle, "w", encoding='utf8', newline='')
        writer = csv.writer(file)
        return file, file_path, writer

    def __get_result_file_path(self, file_path):
        return move_file_to_media_dir(file_path)  # file path in media dir

    def __write(self, df):
        """
        Process the CSV data that are stored on Dask DataFrame.
        Write the calculated rows to a new CSV file in tmp dir
        CSV must have columns: Song, Date, Number of Plays
        """
        row_count = 0
        out_file, out_file_path, writer = self.__get_outfile_writer()
        writer.writerow(["Song", "Date", "Total Number of Plays for Date"])
        song_series = df['Song'].unique()
        for song in song_series:
            song_df = df.query(f'Song == "{song}"')
            date_series = song_df['Date'].unique()
            dates = list(date_series)  # temp solution
            dates.sort(key=lambda date: datetime.strptime(date, '%Y-%m-%d'))
            for d in dates:
                date_df = df.query(f'Date == "{d}" and Song == "{song}"')
                total_play = date_df['Number of Plays'].sum().compute()
                writer.writerow([song, d, total_play])
                row_count += 1
        out_file.close()
        return out_file_path, row_count

    def process(self, source_csv_path):
        """
        Load csv file into Dask DataFrame,
        and process it with __write
        """
        df = dd.read_csv(source_csv_path)
        out_file_path, _ = self.__write(df)
        os.remove(source_csv_path)  # clean up source
        return self.__get_result_file_path(out_file_path)
